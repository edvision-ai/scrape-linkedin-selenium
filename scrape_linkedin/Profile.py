import logging
from sysconfig import get_path
from typing import List

from .ResultsObject import ResultsObject
from .utils import *
from urllib.request import urlopen 
import base64
import re

logger = logging.getLogger(__name__)


class Profile(ResultsObject):
    """Linkedin User Profile Object"""

    attributes = ['personal_info', 'experiences',
                  'skills', 'accomplishments']

    @property
    def personal_info(self):
        logger.info("Trying to determine the 'personal_info' property")
        """Return dict of personal info about the user"""

        personal_info = dict.fromkeys(['name', 'headline', 'company', 'school', 'location',
                                      'summary', 'image', 'followers', 'email', 'phone', 'connected', 'websites'])
        try:
            top_card = one_or_default(self.soup, '.pv-top-card')
            contact_info = one_or_default(self.soup, '.pv-contact-info')

            # Note that some of these selectors may have multiple selections, but
            # get_info takes the first match
            personal_info = {**personal_info, **get_info(top_card, {
                'name': 'h1',
                'headline': '.text-body-medium.break-words',
                'company': 'div[aria-label="Current company"]',
                'school': 'div[aria-label="Education"]',
                'location': '.text-body-small.inline.break-words',
            })}

            summary = text_or_default(
                self.soup, '.pv-about-section', '').replace('... see more', '')

            personal_info['summary'] = re.sub(
                r"^About", "", summary, flags=re.IGNORECASE).strip()

            image_url = ''
            # If this is not None, you were scraping your own profile.
            image_element = one_or_default(
                top_card, 'img.profile-photo-edit__preview')

            if not image_element:
                image_element = one_or_default(
                    top_card, 'img.pv-top-card-profile-picture__image')

            # Set image url to the src of the image html tag, if it exists
            try:
                image_url = image_element['src']
                print(image_url)
                image_url = base64.b64encode(urlopen(image_url).read()).decode('utf-8')
            except:
                pass

            personal_info['image'] = image_url

            activity_section = one_or_default(self.soup,
                                              '.pv-recent-activity-section-v2')

            followers_text = ''
            if activity_section:
                logger.info(
                    "Found the Activity section, trying to determine follower count.")

                # Search for numbers of the form xx(,xxx,xxx...)
                follower_count_search = re.search(
                    r"[^,\d](\d+(?:,\d{3})*) followers", activity_section.text, re.IGNORECASE)

                if follower_count_search:
                    followers_text = follower_count_search.group(1)

                else:
                    logger.debug("Did not find follower count")
            else:
                logger.info(
                    "Could not find the Activity section. Continuing anyways.")

            personal_info['followers'] = followers_text
            personal_info.update(get_info(contact_info, {
                'email': '.ci-email .pv-contact-info__ci-container',
                'phone': '.ci-phone .pv-contact-info__ci-container',
                'connected': '.ci-connected .pv-contact-info__ci-container'
            }))

            personal_info['websites'] = []
            if contact_info:
                websites = contact_info.select('.ci-websites li a')
                websites = list(map(lambda x: x['href'], websites))
                personal_info['websites'] = websites
        except Exception as e:
            logger.exception(
                "Encountered error while fetching personal_info. Details may be incomplete/missing/wrong: %s", e)
        finally:
            return personal_info

    @property
    def experiences(self):
        """
        Returns:
            dict of person's professional experiences.  These include:
                - Jobs
                - Education
                - TODO: Volunteer Experiences
        """
        logger.info("Trying to determine the 'experiences' property")
        experiences = {
            'jobs': [],
            'education': [],
            'volunteer': []
        }
        try:
            embers = self.soup.find_all("section", {"id": re.compile("ember*")})
            for ember in embers:
                header = ember.select("div[class=pvs-header__container]")
                if len(header) == 0:
                    header = get_path_text(ember, [("div", {"class": "display-flex justify-flex-start align-items-center pt3 ph3"})])
                else:
                    header = header[0].text
                content = ember.find(class_="pvs-list__outer-container")
                
                # Parse education.
                if len(header) > 0 and "Education" in header:
                    for edu_section in content.find('ul', {'class': 'ph5'}).find_all('li', {'class': 'artdeco-list__item pvs-list__item--line-separated pvs-list__item--one-column'}):
                        name = get_path_text(edu_section, [('span', {'class': 't-bold'}), ('span', {'aria-hidden': 'true'})])
                        degree = get_path_text(edu_section, [('span', {'class': 't-14 t-normal'}), ('span', {'aria-hidden': 'true'})])
                        field_of_study = ""
                        if len(degree) > 0:
                            degree_split = degree.split(",")
                            if len(degree_split) > 1:
                                field_of_study = degree_split[1]
                                degree = ",".join(degree.split(",")[:-1])
                        date_range = get_path_text(edu_section, [('span', {'class': 't-14 t-normal t-black--light'}), ('span', {'aria-hidden': 'true'})])
                        grades = get_path_text(edu_section, [('div', {'class': 'pv-shared-text-with-see-more t-14 t-normal t-black display-flex align-items-center'}), ('span', {'aria-hidden': 'true'})])
                        experiences['education'].append({'name': name, 'degree': degree, 'date_range': date_range, "field_of_study": field_of_study, "grades": grades})

                # Parse jobs.
                if len(header) > 0 and "Experience" in header:
                    job_section_data = content.find('ul', {'class': 'ph5'})
                    if job_section_data is not None:
                        job_section_data = job_section_data.find_all('li', {'class': 'artdeco-list__item pvs-list__item--line-separated pvs-list__item--one-column'})
                    else:
                        job_section_data = ember.find('ul', {'class': 'pvs-list'}).find_all('li', {'class': 'pvs-list__paged-list-item artdeco-list__item pvs-list__item--line-separated '})
                    for job_section in job_section_data:
                        title = get_path_text(job_section, [('span', {'class': 't-bold'}), ('span', {'aria-hidden': 'true'})])
                        company = get_path_text(job_section, [('span', {'class': 't-14 t-normal'}), ('span', {'aria-hidden': 'true'})])
                        company = company.split("·")[0]
                        date_range, location = '', ''
                        for i, elem in enumerate(job_section.find_all('span', {'class': 't-14 t-normal t-black--light'})):
                            if i == 0:
                                date_range = get_path_text(elem, [('span', {'aria-hidden': 'true'})]).split("·")[0]
                            elif i == 1:
                                location = get_path_text(elem, [('span', {'aria-hidden': 'true'})])
                        description = get_path_text(job_section, [('div', {'class': 'pv-shared-text-with-see-more t-14 t-normal t-black display-flex align-items-center'}), ('span', {'aria-hidden': 'true'})])
                        if len(description) == 0:
                            description = get_path_text(job_section, [('div', {'class': 'display-flex '}), ('span', {'aria-hidden': 'true'})])
                        # Clean the white space in description.
                        description = re.sub(r'\s(?=\s)','',re.sub(r'\s',' ', description))
                        experiences['jobs'].append({'title': title, 'company': company, 'date_range': date_range, "description": description, "location": location})

        except Exception as e:
            logger.exception(
                "Failed while determining experiences. Results may be missing/incorrect: %s", e)
        finally:
            return experiences

    @property
    def skills(self):
        """
        Returns:
            list of skills {name: str, endorsements: int} in decreasing order of
            endorsement quantity.
        """
        logger.info("Trying to determine the 'skills' property")
        skills = self.soup.select('.pv-skill-category-entity__skill-wrapper')
        skills = list(map(get_skill_info, skills))

        # Sort skills based on endorsements.  If the person has no endorsements
        def sort_skills(x): return int(
            x['endorsements'].replace('+', '')) if x['endorsements'] else 0
        return sorted(skills, key=sort_skills, reverse=True)

    @property
    def accomplishments(self):
        """
        Returns:
            dict of professional accomplishments including:
                - publications
                - cerfifications
                - patents
                - courses
                - projects
                - honors
                - test scores
                - languages
                - organizations
        """
        logger.info("Trying to determine the 'accomplishments' property")
        accomplishments = dict.fromkeys([
            'publications', 'certifications', 'patents',
            'courses', 'projects', 'honors',
            'test_scores', 'languages', 'organizations'
        ])
        try:
            container = one_or_default(
                self.soup, '.pv-accomplishments-section')
            for key in accomplishments:
                accs = all_or_default(
                    container, 'section.' + key + ' ul > li')
                accs = map(lambda acc: acc.get_text() if acc else None, accs)
                accomplishments[key] = list(accs)
        except Exception as e:
            logger.exception(
                "Failed to get accomplishments, results may be incomplete/missing/wrong: %s", e)
        finally:
            return accomplishments

    def to_dict(self):
        logger.info(
            "Attempting to turn return a dictionary for the Profile object.")
        return super(Profile, self).to_dict()

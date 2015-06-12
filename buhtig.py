import json
import re
import datetime
import subprocess

from github import GithubException
from github.GithubObject import NotSet
from jira import JIRAError
import requests
import aniso8601
import unidecode as unidecode

from attachments import Attachments


class GithubComet:
    """
       Client used to import issues from a given JIRA project to Github
       by using the new Comet API when possible.
    """

    def __init__(self, jira_project,
                 github, github_organization_name,
                 github_project_name, github_token):

        self.github = github

        self.github_organization = \
            self.github.get_organization(
                github_organization_name)
        self.github_repository = \
            self.github_organization.get_repo(
                github_project_name)

        self.github_organization_name = github_organization_name
        self.github_repository_name = github_project_name
        self.github_token = github_token

        self.github_api_url = 'https://api.github.com/repos/{}/{}/import/issues'.format(
            github_organization_name, github_project_name)

        self.headers = {
            'Accept': 'application/vnd.github.golden-comet-preview+json',
            'Authorization': 'token ' + self.github_token,
            'User-Agent': 'Bobot'
        }

        self.jira_project = jira_project
        self.github_project_milestones = {}
        self.github_organization_members = set()

        [self.github_organization_members.add(member.login) for member in
         self.github_organization.get_members()]

    def format_content(self, issue):
        created = issue.fields.created
        creation_datetime = self._format_date(created)

        try:
            description = self.confluence2markdown(issue.fields.description)
        except:
            description = issue.fields.description

            if description is None:
                description = "*No description*"

        result = '<a href="{}/browse/{}" title="{}">Original issue</a> created by <a href="mailto:{}">{}</a> on {} - {}\n\n<hr />\n\n{}'.format(
            self.jira_project.jira_url, issue.key, issue.key,
            self._spam_protection(issue.fields.reporter.emailAddress),
            issue.fields.reporter.displayName,
            creation_datetime, issue.key, description)

        return result

    def format_comment(self, issue, comment):
        return '<a href="{}/browse/{}?focusedCommentId={}">Original comment</a> posted by <a href="mailto:{}">{}</a> on {}\n\n<hr />\n\n{}'.format(
            self.jira_project.jira_url, issue.key, comment.id,
            self._spam_protection(comment.author.emailAddress.lower()),
            comment.author.displayName, self._format_date(comment.created),
            self.confluence2markdown(comment.body)
        )

    def format_priority(self, issue):
        priority = self.jira_project.get_priority(issue)

        if priority is not None:
            priority = priority.lower()

        return priority

    def format_resolution(self, issue):
        resolution = self.jira_project.get_resolution(issue)

        if resolution is not None:
            resolution = resolution.lower().replace(' ', '-').replace('\'', '')

        return resolution

    def format_type(self, issue):
        return self.jira_project.get_type(issue).lower().replace(' ', '-')

    def create_labels(self, labels):
        for name, color in labels.items():
            self.github_repository.create_label(name, color)

    def delete_labels(self):
        labels = self.github_repository.get_labels()
        [label.delete() for label in labels]

    def create_milestones(self):
        try:
            versions = self.jira_project.get_project_versions()

            for version in versions:
                name = self._uniformize_milestone_name(version.name)

                release_date = NotSet

                try:
                    if version.releaseDate is not None:
                        release_date = datetime.datetime.strptime(
                            version.releaseDate, "%Y-%m-%d")
                except AttributeError:
                    pass

                try:
                    description = version.description
                except AttributeError:
                    description = NotSet

                try:
                    milestone_number = self.github_repository.create_milestone(
                        name, "closed" if version.released else "open",
                        description, release_date
                    ).number

                    self.github_project_milestones[name] = milestone_number

                    print("Milestone {} created".format(name))
                except GithubException:
                    print("Milestone {} already created".format(name))
        except JIRAError:
            print("No project version found for '{}'".format(self.jira_project.project_key))

    @staticmethod
    def confluence2markdown(s):
        s = unidecode.unidecode(s)
        s = s.encode('utf-8')

        (stdout, stderr) = \
            subprocess.Popen(["c2m"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE).communicate(input=s)

        if stderr:
            stdout = s

        return stdout.decode('utf-8')

    @staticmethod
    def _format_date(date):
        return aniso8601.parse_datetime(date).strftime('%d, %b %Y at %H:%M %p')

    @staticmethod
    def _spam_protection(email):
        return email.lower().replace('@', '_AT_')

    @staticmethod
    def _uniformize_milestone_name(name):
        pattern = re.compile(r'(([0-9][.]?)+)')
        identified_version = pattern.search(name).group(0)

        if not 'X' in name and identified_version.count('.') != 2:
            name = pattern.sub(r'\1.0', name)

        return name.strip()

    def import_issues(self, github_attachments_repository_name=None,
                      mapping_usernames=None, default_assignee=None):
        for issue in self.jira_project.get_issues():
            self._import_issue(issue, github_attachments_repository_name,
                               mapping_usernames, default_assignee)

    @staticmethod
    def _append_label(labels, new_label_prefix, new_label):
        if new_label is not None:
            if new_label_prefix is not None:
                new_label = new_label_prefix + new_label

            labels.append(new_label)

    def _import_issue(self, issue, github_attachments_repository_name=None,
                      mapping_usernames=None, default_assignee=None, retry=3):
        key = issue.key
        title = self.jira_project.get_title(issue)
        content = self.format_content(issue)
        created_at = self.jira_project.get_creation_datetime(issue)
        is_closed = self.jira_project.is_closed(issue)
        assignee = self.jira_project.get_assignee(issue)
        milestone = self.jira_project.get_fix_version(issue);

        comments = self._create_comments(issue,
                                         github_attachments_repository_name)

        priority = self.format_priority(issue)

        labels = []

        if priority is not None:
            self._append_label(labels, 'priority:', priority)

        self._append_label(labels, 'resolution:', self.format_resolution(issue))
        self._append_label(labels, 'type:', self.format_type(issue))

        if mapping_usernames is not None:
            mapped_username = mapping_usernames.get(assignee)

            if mapped_username is not None:
                assignee = mapped_username

        assignee = assignee if assignee in self.github_organization_members else default_assignee

        payload = {
            'issue':
                {
                    'title': title,
                    'body': content,
                    'created_at': aniso8601.parse_datetime(
                        created_at).isoformat(),
                    'closed': "true" if is_closed else "false",
                    'labels': labels
                },
            'comments': comments
        }

        if assignee is not None:
            payload['issue'].update({'assignee': assignee})

        if milestone is not None:
            uniformized_milestone = self._uniformize_milestone_name(milestone)

            if uniformized_milestone in self.github_project_milestones:
                payload['issue'].update({'milestone':
                                             self.github_project_milestones[
                                                 uniformized_milestone]})

        pattern = re.compile(r'"(true|false)"')
        payload = json.dumps(payload)
        payload = pattern.sub(r'\1', payload)

        r = requests.post(self.github_api_url,
                          headers=self.headers,
                          data=payload)

        if r.status_code is not 202:
            print("Async import failed for {}: {} {}".format(
                key, r.status_code, r.text))
            print("data=" + payload)
        else:
            self._check_issue_import(issue, github_attachments_repository_name,
                                     default_assignee, key, r.json()['id'],
                                     retry)

    def _check_issue_import(self, issue, github_attachments_repository_name,
                            default_assignee, key, issue_id, retry):
        r = requests.get(self.github_api_url + "/" + str(issue_id),
                         headers=self.headers).json()

        if r['status'] == 'failed':
            print(
                "Import has failed for issue {}:\n{}".format(key, r['errors']))

            if r['errors'][0]['resource'] == 'Internal Error':
                print(
                    "Error was internal, retry is not required since issue should have been imported")
                # if retry > 0 and r['errors'][0]['resource'] == 'Internal Error':
                #     print("Retry in progress for issue " + key)
                #     self._import_issue(issue, github_attachments_repository_name, default_assignee, retry - 1)
        else:
            print("{} imported with success".format(key))

    def _create_comments(self, issue, github_attachments_repository_name):
        result = []

        issue = self.jira_project.get_comments(issue)

        for comment in issue.fields.comment.comments:
            result.append(self._create_comment(issue, comment))

        attachments = self.jira_project.get_attachments(issue)

        if len(
                attachments) > 0 and github_attachments_repository_name is not None:
            items = []

            for attachment in attachments:
                items.append("  - [{}]({})".format(attachment.filename,
                                                   Attachments.get_attachment_url(
                                                       self.github_organization_name,
                                                       github_attachments_repository_name,
                                                       issue.key, attachment)))

            plurial = 's' if len(items) > 1 else ''
            comment = '\n'.join(items)
            comment = 'Attachment' + plurial + ":\n" + comment
            result.insert(0, self._create_raw_comment(comment,
                                                      issue.fields.created))

        return result

    @staticmethod
    def _create_raw_comment(comment, date):
        return {
            'body': comment,
            'created_at': aniso8601.parse_datetime(date).isoformat()
        }

    def _create_comment(self, issue, comment):
        return {
            'body': self.format_comment(issue, comment),
            'created_at': aniso8601.parse_datetime(comment.created).isoformat()
        }

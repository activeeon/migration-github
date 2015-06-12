#!/usr/bin/env python3

from jira import JIRA


class JiraProject:
    """
    Client in charge to retrieve all issues and comments
    for a given JIRA project
    """

    def __init__(self, jira_url, project_key):
        self.jira_url = jira_url
        self.jira_client = JIRA(
            options={'server': self.jira_url, 'verify': False},
            validate=False)
        self.project_key = project_key

    def get_comments(self, issue):
        return self.jira_client.issue(issue.key, expand='comments')

    def get_project_versions(self):
        return self.jira_client.project_versions(self.project_key)

    @staticmethod
    def get_attachments(issue):
        try:
            return issue.fields.attachment
        except AttributeError:
            return None

    @staticmethod
    def get_assignee(issue):
        try:
            return issue.fields.assignee.name
        except AttributeError:
            return None

    @staticmethod
    def get_creation_datetime(issue):
        return issue.fields.created

    @staticmethod
    def get_fix_version(issue):
        try:
            fix_versions = issue.fields.fixVersions

            if len(fix_versions) > 0:
                return fix_versions[0].name
            else:
                return None
        except AttributeError:
            return None

    @staticmethod
    def get_priority(issue):
        try:
            return issue.fields.priority.name
        except AttributeError:
            return None

    @staticmethod
    def get_resolution(issue):
        if issue.fields.resolution is not None:
            return issue.fields.resolution.name
        else:
            return None

    @staticmethod
    def get_title(issue):
        return issue.fields.summary

    @staticmethod
    def get_type(issue):
        return issue.fields.issuetype.name

    @staticmethod
    def is_closed(issue):
        return issue.fields.resolution is not None

    def get_issues(self):
        start_index = 0
        max_nb_results = 100

        result = []

        # while start_index < max_nb_results:
        while True:
            issues = self.jira_client.search_issues(
                'project=' + self.project_key,
                startAt=start_index,
                maxResults=max_nb_results)

            result.extend(issues)

            if len(issues) == 0 or len(issues) < max_nb_results:
                break
            else:
                start_index += max_nb_results

        return sorted(result, key=lambda issue: int(
            issue.key[issue.key.index('-') + 1:]))

    def get_attachment_information(self):
        start_index = 0
        max_nb_results = 100

        result = []

        # while start_index < max_nb_results \
        while True:
            issues = self.jira_client.search_issues(
                'project=' + self.project_key,
                fields='attachment',
                startAt=start_index,
                maxResults=max_nb_results)

            for issue in issues:
                a = self.get_attachments(issue)
                if a is not None and len(a) > 0:
                    [result.append((issue.key, v.id)) for v in a]

            if len(issues) == 0 or len(issues) < max_nb_results:
                break
            else:
                start_index += max_nb_results

        return result

    def get_attachment(self, attachment_id):
        return self.jira_client.attachment(attachment_id)


if __name__ == '__main__':
    jira = JiraProject('https://jira.activeeon.com', 'SCHEDULING')

    print("Attachment ids -> ", str(jira.get_attachment_information()))

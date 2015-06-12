#!/usr/bin/env python3

import os
import tempfile
import urllib
import shutil

from github import Github

import utility

from arij import JiraProject


class Attachments:
    """
    Client in charge to fetch attachments locally from JIRA for a given project
    and then to push retrieved files on a Github repository
    """

    def __init__(self, jira_url,
                 github_organization_name,
                 github_repository_name, working_dir=None):
        """
        :param jira_url: JIRA endpoint used to fetch issues
        :param github_organization_name: organization name where to create repository for attachments
        :param github_repository_name: name of the repository to create for attachments
        :param working_dir: local space where to save attachments temporarily
        """
        self.jira_url = jira_url
        self.github_organization_name = github_organization_name
        self.github_repository_name = github_repository_name

        if working_dir is None:
            self.working_dir = tempfile.TemporaryDirectory(
                suffix='-backup-attachments').name

            print("Working directory set to '{}'".format(self.working_dir))
        else:
            self.working_dir = working_dir

            if not os.path.exists(working_dir):
                os.makedirs(working_dir)

    def fetch_from_jira(self, jira_project_key):
        jira_project = JiraProject(self.jira_url, jira_project_key)
        info = jira_project.get_attachment_information()

        for (issue_key, attachment_id) in info:
            attachment = jira_project.get_attachment(attachment_id)
            issue_id = issue_key[issue_key.index('-') + 1:]
            attachment_folder = self.working_dir + '/' + jira_project.project_key.lower() + '/' + issue_id + '/'

            if not os.path.exists(attachment_folder):
                os.makedirs(attachment_folder)

            with urllib.request.urlopen(attachment.content) as response, open(
                                attachment_folder + '/' + attachment.filename,
                    'wb') as out_file:
                shutil.copyfileobj(response, out_file)
                print("Retrieved attachment '{}' for {}".format(
                    attachment.filename, issue_key))

    def push_on_github(self, github_authentication_token):
        self._create_git_repository(github_authentication_token)

        if utility.execute_command(
                'cd {} && git init && git checkout --orphan gh-pages && {}'.format(
                    self.working_dir,
                    'git remote add origin git@github.com:{}/{}.git'.format(
                        self.github_organization_name,
                        self.github_repository_name))) is 0:
            print("Local git repository and branch created")
        else:
            print("Error while creating local git repository and branch")

        if utility.execute_command(
                'cd {} && git add -A && git commit -m "Import JIRA attachments for selected projects" && git push origin gh-pages'.format(
                    self.working_dir)) is 0:
            print("JIRA attachments backup pushed on Github")
        else:
            print("Error while pushing JIRA attachments backup on Github")

    def _create_git_repository(self, github_authentication_token):
        github = Github(github_authentication_token)
        github_organization = github.get_organization(
            self.github_organization_name)

        github_organization.create_repo(
            self.github_repository_name, has_wiki=False, has_issues=False,
            has_downloads=False)

    def delete_github_repository(self, github_authentication_token):
        github = Github(github_authentication_token)
        github_organization = github.get_organization(
            self.github_organization_name)
        try:
            github_organization.get_repo(self.github_repository_name).delete()
        except:
            pass

    def delete_working_dir(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    @staticmethod
    def get_attachment_url(github_attachments_organization_name,
                           github_attachments_repository_name,
                           jira_issue_key, attachment):
        (project_key, issue_key_id) = jira_issue_key.split('-')

        return 'https://github.com/{}/{}/blob/gh-pages/{}/{}/{}'.format(
            github_attachments_organization_name, github_attachments_repository_name,
            project_key.lower(), issue_key_id, attachment.filename)


if __name__ == '__main__':
    attachments = Attachments('https://jira.activeeon.com',
                              "ow2-github-migration",
                              'attachments-jira')

    github_token = utility.get_env_var("GITHUB_TOKEN")

    attachments.delete_working_dir()
    attachments.delete_github_repository(github_token)

    attachments.fetch_from_jira('SCHEDULING')
    attachments.push_on_github(github_token)
    attachments.delete_working_dir()

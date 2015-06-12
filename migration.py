#!/usr/bin/env python3

import argparse
import tempfile

import argh
from github.GithubObject import NotSet

from attachments import Attachments
import utility
import buhtig
import arij

__author__ = 'lpellegr'

from github import Github
import os
import re


class Migration:
    def __init__(self):
        self.github = Github(github_authentication_token)
        self.github_organization = self.github.get_organization(
            github_organization_name)
        self.repositories = \
            self.load_data("mapping-repositories.txt", lambda data,
                                                              chunks: self._create_repository_entries(
                data, chunks))

    @staticmethod
    def _create_repository_entries(data, chunks):
        github_repo_name = chunks[0]

        if len(chunks) > 1:
            github_repo_name = chunks[1]

        data.append(RepositoryMappingEntry(chunks[0], github_repo_name))

    def get_repository(self, github_repo_name):
        return self.github_organization.get_repo(github_repo_name)

    def create_repositories(self):
        [self.create_repository(r.github_repo_name) for r in self.repositories]

    def create_repository(self, github_repo_name):
        utility.execute(
            lambda: self.github_organization.create_repo(
                github_repo_name, has_wiki=False, has_issues=False,
                has_downloads=True),
            "Repository " + github_repo_name + " created",
            "Cannot create repository '" + github_repo_name + "' since it already exists")

    def delete_repositories(self):
        [self.delete_repository(r.github_repo_name) for r in self.repositories]

    def delete_repository(self, github_repo_name):
        utility.execute(
            lambda: self.get_repository(github_repo_name).delete(),
            "Repository " + github_repo_name + " deleted",
            "Cannot delete repository '" + github_repo_name + "' since it does not exist")

    def edit_repositories(self, description=None, homepage=None, private=None,
                          has_issues=None, has_wiki=None, default_branch=None):
        [self.edit_repository(r.github_repo_name, description, homepage,
                              private, has_issues, has_wiki, default_branch) for
         r in self.repositories]

    def edit_repository(self, github_repo_name, description=NotSet,
                        homepage=NotSet, private=NotSet, has_issues=NotSet,
                        has_wiki=NotSet, default_branch=NotSet):
        repo = self.get_repository(github_repo_name)

        description = Migration.transform_string(description)
        homepage = Migration.transform_string(homepage)
        private = Migration.transform_bool(private)
        has_issues = Migration.transform_bool(has_issues)
        has_wiki = Migration.transform_bool(has_wiki)
        default_branch = Migration.transform_string(default_branch)

        utility.execute(
            lambda: repo.edit(github_repo_name, description, homepage, private,
                              has_issues, has_wiki, default_branch),
            "Repository " + github_repo_name + " edited",
            "Cannot edit repository '" + github_repo_name + "' since it does not exist")

    def clone_repositories(self, working_dir=None):
        if working_dir is None:
            working_dir = tempfile.TemporaryDirectory(
                suffix='github-migration').name

        [self.clone_repository(r.ow2_repo_name, working_dir) for r in
         self.repositories]

    @staticmethod
    def clone_repository(ow2_repo_name, working_dir):
        repo_dir = working_dir + os.sep + ow2_repo_name

        if not os.path.exists(repo_dir):
            print("Cloning repository {} in {}".format(ow2_repo_name, repo_dir))

            command = "git clone --mirror {} {}".format(
                "git://gitorious.ow2.org/{}/{}.git".format(
                    ow2_organization_name,
                    ow2_repo_name),
                repo_dir)

            if utility.execute_command(command) is 0:
                print("Repository '{}' has been cloned".format(ow2_repo_name))
            else:
                print("Error occurred while cloning '{}'".format(ow2_repo_name))
        else:
            if utility.execute_command(
                    "cd {}; git remote update".format(repo_dir)) is 0:
                print("Repository '{}' has been updated".format(ow2_repo_name))
            else:
                print(
                    "Error occurred while updating '{}'".format(ow2_repo_name))

    def gc_repositories(self, working_dir=None):
        if working_dir is None:
            raise ValueError("Undefined argument --working-dir")

        [self.gc_repository(r.ow2_repo_name, working_dir) for r in
         self.repositories]

    @staticmethod
    def gc_repository(ow2_repo_name, working_dir):
        repo_dir = working_dir + os.sep + ow2_repo_name
        command = "cd {} && git reflog expire --expire=now --all && git gc --aggressive --prune=now && git repack -a -d -l".format(
            repo_dir)

        print("Executing command '{}'".format(command))

        if utility.execute_command(command) is 0:
            print(
                "Repository '{}' has been garbage collected".format(
                    ow2_repo_name))
        else:
            print("Error occurred while garbage collecting '{}'".format(
                ow2_repo_name))

    def prune_repositories(self, working_dir=None):
        filters = self.load_data("mapping-filters.txt",
                                 lambda data, chunks: data.append(
                                     FilterMappingEntry(chunks[0], chunks[1])))
        for f in filters:
            self.prune_repository(f, working_dir)

    @staticmethod
    def prune_repository(entry, working_dir):
        repo_dir = working_dir + os.sep + entry.ow2_repo_name
        command = "java -jar {} --delete-files {} {}".format(bfg_jar_path,
                                                             entry.bfg_filter,
                                                             repo_dir)

        print("Executing command '{}'".format(command))

        if utility.execute_command(command) is 0:
            command = \
                'cd {} && git reflog expire --expire=now --all && git gc --prune=now --aggressive'.format(
                    repo_dir)

            print("Executing command '{}'".format(command))

            if utility.execute_command(command) is 0:
                print(
                    "Repository '{}' has been pruned".format(
                        entry.ow2_repo_name))
        else:
            print(
                "Error occurred while pruning '{}'".format(entry.ow2_repo_name))

    def import_repositories(self, working_dir=None):
        if working_dir is None:
            raise ValueError("Undefined argument --working-dir")

        # Sort repositories by Github name, in reverse order. This way
        # they will be imported so that at the end they appear
        # lexicographically sorted on Github
        sorted_repositories = sorted(self.repositories,
                                     key=lambda r: r.github_repo_name,
                                     reverse=True)
        [self.import_repository(r, working_dir) for r in sorted_repositories]

    @staticmethod
    def import_repository(entry, working_dir):
        repo_dir = working_dir + os.sep + entry.ow2_repo_name
        github_url = "git@github.com:{}/{}.git".format(github_organization_name,
                                                       entry.github_repo_name)

        if utility.execute_command(
                "cd {} && git push --mirror {}".format(repo_dir,
                                                       github_url)) is 0:
            print(
                "Repository '{}' has been imported".format(entry.ow2_repo_name))
        else:
            print("Error occurred while importing '{}' to Github".format(
                entry.ow2_repo_name))

    @staticmethod
    def load_data(file, appender):
        data = []

        with open(file, "r") as f:
            lines = f.read().splitlines()

        for line in lines:
            if not line.startswith("#") and len(line) > 0:
                chunks = re.split('\s+', line)
                appender(data, chunks)

        return data

    def import_attachments(self, jira_endpoint,
                           github_attachments_repository_name,
                           working_dir=None):
        attachments = Attachments(jira_endpoint,
                                  github_organization_name,
                                  github_attachments_repository_name,
                                  working_dir=working_dir)

        for entry in self._load_issues_mapping():
            self.import_attachments_for_project(attachments,
                                                entry.jira_project_key)

        attachments.push_on_github(github_authentication_token)

    @staticmethod
    def import_attachments_for_project(attachments, jira_project_key):
        attachments.fetch_from_jira(jira_project_key)

    def import_issues(self, jira_endpoint, github_attachments_repository_name,
                      default_assignee=None):
        mapping_usernames = self._load_usernames_mapping()

        for entry in self._load_issues_mapping():
            print(
                "Importing issues from JIRA project {} to Github repository named '{}'".format(
                    entry.jira_project_key, entry.github_project_name))

            self.import_issues_for_project(jira_endpoint,
                                           entry.jira_project_key,
                                           entry.github_project_name,
                                           github_attachments_repository_name,
                                           mapping_usernames,
                                           default_assignee)

    def _load_issues_mapping(self):
        return self.load_data("mapping-issues.txt",
                              lambda data, chunks: data.append(
                                  IssueMappingEntry(chunks[0], chunks[1])))

    def _load_usernames_mapping(self):
        result = {}

        self.load_data("mapping-usernames.txt",
                       lambda data, chunks:
                       result.update({chunks[0]: chunks[1]}))

        return result

    def import_issues_for_project(self, jira_endpoint, jira_project_key,
                                  github_project_name,
                                  github_attachments_repository_name=None,
                                  mapping_usernames=None,
                                  default_assignee=None):
        jira_project = arij.JiraProject(jira_endpoint, jira_project_key)
        github_comet = buhtig.GithubComet(jira_project, self.github,
                                          github_organization_name,
                                          github_project_name,
                                          github_authentication_token)

        # delete default labels created by Github
        github_comet.delete_labels()
        # create custom default labels
        github_comet.create_labels({
            # labels related to issue priority
            'priority:blocker': 'ff6666',
            'priority:critical': 'ff8080',
            'priority:major': 'ff9999',
            'priority:minor': 'ffb2b2',
            'priority:trivial': 'ffcccc',
            # labels related to issue resolution
            'resolution:cannot-reproduce': 'bfe5bf',
            'resolution:duplicate': 'bfe5bf',
            'resolution:fixed': 'bfe5bf',
            'resolution:incomplete': 'bfe5bf',
            'resolution:invalid': 'bfe5bf',
            'resolution:wont-fix': 'bfe5bf',
            # labels related to issue type
            'type:bug': 'c7def8',
            'type:improvement': 'c7def8',
            'type:new-feature': 'c7def8',
            'type:story': 'c7def8',
            'type:story-item': 'c7def8',
            'type:task': 'c7def8',
            'type:task-related-bug': 'c7def8'
        })
        github_comet.create_milestones()
        github_comet.import_issues(github_attachments_repository_name,
                                   mapping_usernames, default_assignee)

    @staticmethod
    def transform_bool(v):
        if v is None:
            return NotSet
        else:
            return Migration.str2bool(v)

    @staticmethod
    def transform_string(v):
        if v is None:
            return NotSet
        else:
            return v

    @staticmethod
    def str2bool(v):
        return v.lower() in ("yes", "true", "t", "1")


class FilterMappingEntry:
    def __init__(self, ow2_repo_name, bfg_filter):
        self.ow2_repo_name = ow2_repo_name
        self.bfg_filter = bfg_filter

    def __str__(self):
        return "{} {}".format(self.ow2_repo_name, self.bfg_filter)


class IssueMappingEntry:
    def __init__(self, jira_project_key, github_project_name):
        self.jira_project_key = jira_project_key
        self.github_project_name = github_project_name


class RepositoryMappingEntry:
    def __init__(self, ow2_repo_name, github_repo_name):
        self.ow2_repo_name = ow2_repo_name
        self.github_repo_name = github_repo_name

    def __str__(self, *args, **kwargs):
        return "OW2={} \t\t\t\t Github={}".format(self.ow2_repo_name,
                                                  self.github_repo_name)


def main():
    github_subcommands = [
        migration.create_repositories,
        migration.delete_repositories,
        migration.edit_repositories,
        migration.import_repositories,
        migration.import_attachments,
        migration.import_issues,
        migration.import_issues_for_project
    ]

    ow2_subcommands = [
        migration.clone_repositories,
        migration.gc_repositories,
        migration.prune_repositories
    ]

    parser = argparse.ArgumentParser()
    argh.add_commands(parser, github_subcommands, namespace='github')
    argh.add_commands(parser, ow2_subcommands, namespace='ow2')
    argh.dispatch(parser)


if __name__ == "__main__":
    from requests.packages import urllib3

    urllib3.disable_warnings()

    try:
        bfg_jar_path = utility.get_env_var("BFG_JAR_PATH")
        github_authentication_token = utility.get_env_var("GITHUB_TOKEN")
        github_organization_name = utility.get_env_var("GITHUB_ORGANIZATION")
        ow2_organization_name = utility.get_env_var("OW2_ORGANIZATION")

        migration = Migration()
        main()
    except utility.UndefinedEnvironmentVariable as e:
        utility.error("Undefined environment variable: {}".format(e.var_name))

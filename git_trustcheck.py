#!/usr/bin/python3
"""
git-trustcheck checks commits for being singed with repo-specific trusted
               gpg signature and supports managing of repo-specific gpg homes

See git-trustcheck.py --help

Copyright (C) 2014 Tocho Tochev (tocho AT tochev DOT net)

MIT License
"""

VERSION = "0.1.0"

import argparse
import os
import re
import subprocess
import sys
import textwrap
try:
    import gpgme
except ImportError:
    gpgme = None


DEFAULT_REVISION_RANGE = '@{1}..@{0}'


class GitTrustChecker(object):

    def __init__(self,
                 verbose=False,
                 run_path=None,
                 gpg_home=None,
                 disable_gpgme=None,
                 keys_file=None):
        self.verbose        = verbose
        self.run_path       = run_path
        self.gpg_home       = gpg_home
        self.disable_gpgme  = disable_gpgme

        self.git_home       = self.get_git_home()
        self.gpg_home       = self.gpg_home or self.get_gpg_home_from_git()
        self.keys_file      = keys_file or os.path.join(self.git_home,
                                                        'trusted_keys')
        self.gpg_program    = os.path.join(self.git_home, 'gpg_with_home')

    def get_git_home(self):
        return os.path.join(self.git_output('rev-parse',
                                            '--show-toplevel').decode().strip(),
                            '.git')

    def get_gpg_home_from_git(self):
        home = self.git_output_or_None('config', 'gpg.home')
        return home and home.decode().strip()

    def git_output(self, *args, **kwargs):
        if self.run_path:
            args = ('-C', self.run_path) + args
        args = ('git',) + args
        env = os.environ.copy()
        if self.gpg_home:
            env["GNUPGHOME"] = self.gpg_home
        return subprocess.check_output(args, env=env, **kwargs)

    def git_output_or_None(self, *args, **kwargs):
        try:
            return self.git_output(*args, **kwargs)
        except subprocess.CalledProcessError:
            return None

    def _create_gpg_home_or_exit(self):
        if not os.path.exists(self.gpg_home):
            try:
                os.mkdir(self.gpg_home, mode=0o700)
                with open(os.path.join(self.gpg_home, "gpg.conf"), 'w') as conf:
                    conf.write(GPG_CONF_HARDENED)
            except IOError as e:
                print(e, file=sys.stderr)
                exit(1)

    def _create_gpg_program_or_exit(self):
        try:
            with open(self.gpg_program, 'w') as f:
                f.write(GPG_WITH_HOME_SCRIPT.format(gpg_home=self.gpg_home))
            os.chmod(self.gpg_program, 0o755)
        except IOError as e:
                print(e, file=sys.stderr)
                exit(1)

    def setup_gpg_home(self):
        if not self.gpg_home:
            self.gpg_home = os.path.join(self.git_home, 'gpg_home')
        self._create_gpg_home_or_exit()
        self._create_gpg_program_or_exit()
        self.git_output('config', 'gpg.home', self.gpg_home)
        self.git_output('config', 'gpg.program', self.gpg_program)
        self.git_output('config', 'alias.gpg', '!' + self.gpg_program)

    def unset_gpg_home(self):
        self.git_output_or_None('config', '--unset-all', 'gpg.home')
        self.git_output_or_None('config', '--unset-all', 'gpg.program')
        self.git_output_or_None('config', '--unset-all', 'alias.gpg')
        if os.path.exists(self.gpg_program):
            print("Not deleting `%s'" % self.gpg_program, file=sys.stderr)
        if self.gpg_home and os.path.exists(self.gpg_home):
            print("Not deleting `%s'" % self.gpg_home, file=sys.stderr)
        # TODO: add delete files option

    def get_trusted_keys(self):
        store_file = self.keys_file
        if os.path.exists(store_file):
            keys = set()
            with open(store_file, 'r') as store:
                for line in store.readlines():
                    data = line.split('#', 1)[0].strip()
                    if not data:
                        continue
                    elif re.match('[0-9a-f]{8,}', data):
                        # data is a keyid
                        set.add(data.upper())
                    else:
                        keys.update(self.get_keyids(data))
            return keys
        else:
            print("WARNING: Unable to open key store. "
                  "Allowing all trusted keys.",
                  file=sys.stderr)
        return {'*'}

    def check_gpgme(self):
        if not self.disable_gpgme:
            if gpgme:
                return True
            else:
                print("Warning: python3 gpgme library not present.\n"
                      "Warning: query to keyid and keyid to owner disabled.",
                      file=sys.stderr)
                self.disable_gpgme = True
        return False

    def add_trusted_key(self, key):
        with open(self.keys_file, 'a') as store:
            store.write(key + '\n')

    def edit_trusted_keys(self):
        # should be `edit [self.keys_file]' but on Arch /usr/bin/edit->ex
        subprocess.call([os.environ.get('EDITOR', '') or 'vim', self.keys_file])

    def remove_key(self, key):
        # TODO: maybe implement
        raise NotImplemented

    def list_trusted_keys(self):
        keys = sorted(self.get_trusted_keys())
        for key in keys:
            print(key + '    ' + ' | '.join(self.get_key_owner(key)))

    def _log2commits(self, log_output):
        commits_data = re.findall(r'.*?^[0-9a-f]{40}',
                                  log_output,
                                  re.IGNORECASE | re.DOTALL | re.MULTILINE)
        keys = self.get_trusted_keys()
        if self.verbose:
            print("Trusted keys:\n" + '\n'.join(sorted(keys)))
            print()

        commits = [Commit(commit_text, keys) for commit_text in commits_data]

        if self.verbose:
            print("Commits:\n" + '\n'.join(
                ["{0} T:{1:d} G:{2:d} V:{3:d} key:{4}".format(
                        commit.id,
                        commit.trusted, commit.good, commit.valid,
                        commit.key
                    )
                for commit in commits]))
            print()

        return commits

    def get_not_trusted(self, revision_query, ignore_child_trust=False):
        output = self.git_output('log',
                                '--pretty=format:%H', '--show-signature',
                                *revision_query)
        commits = self._log2commits(output.decode())

        if ignore_child_trust:
            not_trusted_commits = [commit.id for commit in commits
                                   if not commit.trusted]
            query = revision_query
        else:
            trusted_ids = [commit.id for commit in commits
                        if commit.trusted]
            exclude_trusted = ['^' + commit_id for commit_id in trusted_ids]

            query = list(revision_query) + exclude_trusted

            not_trusted_commits = self.git_output(
                                        'log', '--pretty=format:%H',
                                        *query
                                    ).decode().splitlines()
        return not_trusted_commits, query

    def find_not_trusted(self, revision_query,
                         ignore_child_trust=False,
                         silent=False,
                         exit_code=False):
        try:
            not_trusted_commits, query = \
                self.get_not_trusted(revision_query, ignore_child_trust)
        except subprocess.CalledProcessError:
            print("Failed to execute a git command!", file=sys.stderr)
            # FIXME: maybe behave differently
            raise

        if not silent or self.verbose:
            print('git query:\n' + ' '.join(query) + '\n')

        if not silent or self.verbose:
            if not_trusted_commits:
                print("commits not trusted:")
            else:
                print("all commits in the supplied range are trusted")
        if not_trusted_commits:
            print('\n'.join(not_trusted_commits))
            if exit_code:
                exit(1)

    def get_gpgme_context(self):
        context = gpgme.Context()
        if self.gpg_home:
            context.set_engine_info(context.protocol, None, self.gpg_home)
        return context

    def get_keyids(self, gpg_query):
        return set(subkey.keyid
                   for key in self.get_gpgme_context().keylist(gpg_query)
                   for subkey in key.subkeys
                   if subkey.can_sign and not (subkey.invalid or
                                               subkey.revoked or
                                               subkey.expired))

    def get_key_owner(self, keyid):
        return ['{0} ({1})'.format(uid.name, uid.email)
                for key in self.get_gpgme_context().keylist(keyid)
                for uid in key.uids]



class Commit(object):
    """
    Stores signature status information about a comit
    """

    def __init__(self, log_text="", keys=frozenset()):
        self.id = log_text.strip().splitlines()[-1]
        self.key = None
        self.good = False           # Good according to git
        self.valid = False          # Valid - no warnings or errors
        self.trusted = False
        #format:
        # gpg: Signature made [timestamp maybe with newline]
        # gpg:                using RSA key [KEYID]
        # gpg: Good signature from "[USER]"
        # gpg: WARNING: This subkey has been revoked by its owner!
        # gpg: reason for revocation: No reason specified
        # [commit hash with signature]
        # [commit hash without signature]

        key_match = re.search('using \\w+ key(?: ID)? ([0-9a-f]*)$',
                              log_text,
                              re.IGNORECASE | re.MULTILINE)
        if key_match:
            self.key = key_match.groups()[0]
            self.good = bool(re.search('^gpg: Good signature',
                                       log_text,
                                       re.MULTILINE))
            self.valid = (self.good and
                          not (re.search('^gpg: (WARNING|ERROR)',
                                         log_text,
                                         re.MULTILINE | re.IGNORECASE)))
            self.trusted = self.is_trusted(keys)

    def is_trusted(self, keys):
        if not self.good or not self.valid:
            return False
        if '*' in keys:
            return True
        else:
            return any(key.upper().endswith(self.key.upper())
                       for key in keys)


GPG_WITH_HOME_SCRIPT = textwrap.dedent(r"""\
#!/bin/sh
if [ "$GNUPGHOME"x = "x" ]; then
  GNUPGHOME={gpg_home}
fi
GNUPGHOME=$GNUPGHOME gpg "$@"
""")

GPG_CONF_HARDENED = textwrap.dedent("""\
# personal digest preferences
personal-digest-preferences SHA512

# message digest algorithm used when signing a key
cert-digest-algo SHA512

# Set the list of default preferences to string.
# used for new keys and default for "setpref"
default-preference-list SHA512 SHA384 SHA256 SHA224 AES256 AES192 AES CAST5 ZLIB BZIP2 ZIP Uncompressed

# display long keyids - may cause problem with badly written scripts
keyid-format long
""")


#TODO: maybe do something with the trust warning, probably not
#TRUST_WARN='gpg: WARNING: This key is not certified with a trusted signature!'

def create_git_trustcheck_args_parser():
    parser = argparse.ArgumentParser(
        prog='git-trustcheck',
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent("""\
        Checks commits for having repo-specific trusted gpg signature and outputs commits that are not trusted.
        Additionally supports managing of repo-specific gpg homes.

        The keyids are kept in REPO_ROOT/.git/trusted_keys one per line.
        Optionally they may be a gpg query (such as user@example.com) or * (for allowing all keys trusted by the gpg store).
        In the file '#' discards everything until the end of the line.

        A repo-specific gpg home can be created by --setup-gpg-home.
        In this case the gpg home is put in REPO_ROOT/.git/gpg with a hardened gpg.conf, git is instructed to use gpg via the REPO_ROOT/.git/git_with_home script, which call gpg with the specific gpg home.
        """))


    trust_check = parser.add_argument_group("Output not-trusted")
    parser.add_argument('revision_query',
                        type=str,
                        default=[DEFAULT_REVISION_RANGE],
                        nargs='*',
                        help="revision range to check (default %s)" %
                                DEFAULT_REVISION_RANGE)
    main_group = parser.add_mutually_exclusive_group()
    main_group.add_argument('--setup-gpg-home',
                            dest='setup_gpg_home',
                            action='store_true',
                            default=False,
                            #FIXME: maybe the help here is too much?
                            help=textwrap.dedent("""\
                                create repository specific gpg home
                                 - creates .git/gpg or the `-G' parameter
                                 - creates script .git/gpg_with_home
                                 - git config gpg.home and gpg.program
                                 - creates git alias `gpg' for gpg.program"""))
    main_group.add_argument('--unset-gpg-home',
                            dest='unset_gpg_home',
                            action='store_true',
                            default=False,
                            help="disable repository specific gpg home\n"
                                 "essentially undoes --setup-gpg-home\n"
                                 "(no data is deleted)")
    main_group.add_argument('-c', '--ignore-child-trust',
                            dest='ignore_child_trust',
                            action='store_true',
                            default=False,
                            help="by default if a child is trustworthy "
                                 "so is the parent\n"
                                 "(note that in this mode the git query is the "
                                 "one supplied to this program)")
    main_group.add_argument('-l', '--list-trusted',
                            dest='list_trusted',
                            action='store_true',
                            default=False,
                            help="list trusted keys for this project")
    main_group.add_argument('-a', '--add-key',
                            dest='add_key',
                            type=str,
                            help="add key id or gpg query")
    main_group.add_argument('-E', '--edit-trusted',
                            dest='edit_trusted',
                            action='store_true',
                            default=False,
                            help="open the trusted keys file in an editor")

    #TODO: add remove-key

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument('-v', '--verbose',
                              action='store_true',
                              default=False,
                              help="output additional information")
    output_group.add_argument('-s', '--silent',
                              dest='silent',
                              action='store_true',
                              default=False,
                              help="do not show the summary header,\n"
                                   "do not show git query for the untrusted "
                                   "commits")

    config = parser.add_argument_group("configuration")

    config.add_argument('-e', '--exit-code',
                        dest='exit_code',
                        action='store_true',
                        default=False,
                        help="exit with 0x01 if untrusted commits are found")
    config.add_argument('-C',
                        dest='run_path',
                        type=str,
                        help="run path, same as git -C")
    config.add_argument('-K',
                        dest='keys_file',
                        type=str,
                        help="location of the keys file")
    config.add_argument('-G',
                        dest='gpg_home',
                        type=str,
                        help="gpg homedir, also can be set through $GNUPGHOME")
    config.add_argument('--disable-gpgme',
                        dest='disable_gpgme',
                        action='store_true',
                        default=False,
                        help="disable gpgme,\n"
                             "disables query to keyid and "
                             "keyid to owner functionality")

    parser.add_argument('--version',
                        action='version',
                        version="%(prog)s " + VERSION)

    return parser


def main():
    parser = create_git_trustcheck_args_parser()

    args = parser.parse_args()

    trust_checker = GitTrustChecker(verbose=args.verbose,
                                    run_path=args.run_path,
                                    gpg_home=args.gpg_home,
                                    disable_gpgme=args.disable_gpgme,
                                    keys_file=args.keys_file)

    if args.list_trusted:
        trust_checker.list_trusted_keys()
    elif args.setup_gpg_home:
        trust_checker.setup_gpg_home()
    elif args.unset_gpg_home:
        trust_checker.unset_gpg_home()
    elif args.add_key:
        trust_checker.add_trusted_key(args.add_key)
    elif args.edit_trusted:
        trust_checker.edit_trusted_keys()
    else:
        trust_checker.find_not_trusted(args.revision_query,
                                       args.ignore_child_trust,
                                       args.silent,
                                       args.exit_code)


if __name__ == '__main__':
    main()

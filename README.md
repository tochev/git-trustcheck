# git-trustcheck #

**git-trustcheck** is a tool for checking commit history for untrusted commits
and managing per-repository gpg configurations.

*Homepage:* https://github.com/tochev/git-trustcheck

## Install ##

Install `python3` and `python3-gpgme`:

    apt-get install python3 python3-gpgme

Get the project:

    git clone https://github.com/tochev/git-trustcheck

Optional: create `git-trustcheck` symlink to `git_trustcheck.py` in
order to be able to call `git trustcheck`:

    sudo ln -s GIT_TRUSTCHECK_DIR/git_trustcheck.py /usr/bin/git-trustcheck

## Example Usage ##

### Usage ###

    $ git-trustcheck --help

    usage: git-trustcheck [-h]
                          [--setup-gpg-home | --unset-gpg-home | -c | -l | -a ADD_KEY | -E]
                          [-v | -s] [-e] [-C RUN_PATH] [-K KEYS_FILE]
                          [-G GPG_HOME] [--disable-gpgme] [--version]
                          [revision_query [revision_query ...]]

    Checks commits for having repo-specific trusted gpg signature and outputs
    commits that are not trusted.
    Additionally supports managing of repo-specific gpg homes.

    The keyids are kept in REPO_ROOT/.git/trusted_keys one per line.
    Optionally they may be a gpg query (such as user@example.com) or *
    (for allowing all keys trusted by the gpg store).
    In the file '#' discards everything until the end of the line.

    A repo-specific gpg home can be created by --setup-gpg-home.
    In this case the gpg home is put in REPO_ROOT/.git/gpg with a hardened 
    gpg.conf, git is instructed to use gpg via the REPO_ROOT/.git/git_with_home
    script, which call gpg with the specific gpg home.

    positional arguments:
      revision_query        revision range to check (default @{1}..@{0})

    optional arguments:
      -h, --help            show this help message and exit
      --setup-gpg-home      create repository specific gpg home
                             - creates .git/gpg or the `-G' parameter
                             - creates script .git/gpg_with_home
                             - git config gpg.home and gpg.program
                             - creates git alias `gpg' for gpg.program
      --unset-gpg-home      disable repository specific gpg home
                            essentially undoes --setup-gpg-home
                            (no data is deleted)
      -c, --ignore-child-trust
                            by default if a child is trustworthy so is the parent
                            (note that in this mode the git query is the one supplied to this program)
      -l, --list-trusted    list trusted keys for this project
      -a ADD_KEY, --add-key ADD_KEY
                            add key id or gpg query
      -E, --edit-trusted    open the trusted keys file in an editor
      -v, --verbose         output additional information
      -s, --silent          do not show the summary header,
                            do not show git query for the untrusted commits
      --version             show program's version number and exit

    configuration:
      -e, --exit-code       exit with 0x01 if untrusted commits are found
      -C RUN_PATH           run path, same as git -C
      -K KEYS_FILE          location of the keys file
      -G GPG_HOME           gpg homedir, also can be set through $GNUPGHOME
      --disable-gpgme       disable gpgme,
                            disables query to keyid and keyid to owner functionality

### Examples ###

    ### situation
    $ git pull
    $ git log --show-signature '--pretty=format:%H %s'
    fee04ebd7adee5b19f33794864f91a500f92e4d8 msg6_unsigned
    1615c388edee3003f6dad059835f2b21e33bf69b msg5_unsigned
    gpg: Signature made 2014-05-24T14:08:01 EEST
    gpg:                using RSA key E5C243B7300F75B8
    gpg: Good signature from "TesterB <testerB@example.com>"
    c993c09d083ff539498cdff4d6927153ca73c31b msg4
    6e0fa1b4c87b8d5e191ca53cf912aa20fcead2ea msg3_unsigned
    gpg: Signature made 2014-05-24T14:08:01 EEST
    gpg:                using RSA key 97B6F762E762289C
    gpg: Good signature from "TesterA <testerA@example.com>"
    dccfe88f7d9a90d6ffbead766d6291fa8827ca8c msg2
    08b3018653e227ba6fa1a24882ec34be3753f508 msg1_unsigned

    ### show untrusted in '@{1}..@{0}'
    $ git trustcheck
    WARNING: Unable to open key store. Allowing all trusted keys.
    git query:
    @{1}..@{0} ^c993c09d083ff539498cdff4d6927153ca73c31b

    commits not trusted:
    fee04ebd7adee5b19f33794864f91a500f92e4d8
    1615c388edee3003f6dad059835f2b21e33bf69b

    ### show untrusted in HEAD discarding child trust
    $ git trustcheck HEAD -c
    WARNING: Unable to open key store. Allowing all trusted keys.
    git query:
    HEAD

    commits not trusted:
    fee04ebd7adee5b19f33794864f91a500f92e4d8
    1615c388edee3003f6dad059835f2b21e33bf69b
    6e0fa1b4c87b8d5e191ca53cf912aa20fcead2ea
    08b3018653e227ba6fa1a24882ec34be3753f508

    ### add only TesterA to trusted
    $ git trustcheck -a 97B6F762E762289C

    ### show untrusted in '@{1}..@{0}', now TesterB is not trusted
    $ git trustcheck
    git query:
    @{1}..@{0}

    commits not trusted:
    fee04ebd7adee5b19f33794864f91a500f92e4d8
    1615c388edee3003f6dad059835f2b21e33bf69b
    c993c09d083ff539498cdff4d6927153ca73c31b
    6e0fa1b4c87b8d5e191ca53cf912aa20fcead2ea

    ### create repo-specific gpg repo
    $ git trustcheck --setup-gpg-home
    $ gpg --export-secret-keys 97B6F762E762289C | git gpg --import
    $ gpg --export-ownertrust | grep 97B6F762E762289C | git gpg --import-ownertrust
    $ # delete key form normal home
    $ echo a >> a.txt && git add a.txt && git commit -m gpg_local -S97B6F762E762289C
    [master 0a8145f] gpg_local
     1 file changed, 1 insertion(+)
    # trustcheck ok
    $ git trustcheck
    git query:
    @{1}..@{0} ^0a8145fa29d3d721f284951e3122b1b1a1dace23

    all commits in the supplied range are trusted
    # the last commit is trusted

## Motivation ##

I needed a way to easily find commits that have not been signed so I
could review them and approve the changes by signing them. Additionally,
I had several repositories for which I needed to be able to verify that
the contents have not been tampered with, either on the way to or from
the remote repository.

So the initial version was just a git hook that checked for the strange
behavior and a git alias for listing the untrusted commits.

As time progressed I accumulated a fair bit of different keys for the
different projects I was involved with, and I also had to import into my
gpg home a lot of keys from other developer which I trusted to different
degrees. This made my keyring messy and manual commit log inspection
tedious, especially during branch merges.

Therefore I decided that it would be most convenient to have per
repository gpg store, which would also help me verify signatures made by
keys with which I normally would not want to pollute my keyring.

## Status ##

The command line API is fixed for the time being but the source
structure will most likely be refactored in the near future.

## Limitations ##

I have tried to make this program error on the side of safety. I'm using
it myself for my repositories.

That being said, you should be aware of what are you doing and what are
the underlying limitations of git and gpg. You should not update their
configuration or execution preferences from the repository you are
checking.

For instance if you are using this script to track your dotfiles repo,
to which your dotfiles are symlinked, you should first fetch the remote,
check the remote using `git trustcheck origin/master` and after that
merge it to `master`.

You should not symlink githooks, gpg configuration, git configuration, or
this program's configuration to the repo you are monitoring.

Use wisely and be safe.

## License ##

Distributed under MIT licence.

## Authors ##

Developed by Tocho Tochev [tocho AT tochev DOT net].

    GPG key: 4096R/06B57E9483240480
    fingerprint: BF1E F283 C6AC 6E9C 710F  4F84 06B5 7E94 8324 0480

## FAQ ##

#### Why sign commits? ####

Read http://mikegerwitz.com/papers/git-horror-story.html

#### What was your motivation? ####

See the "Motivation" section.

#### Am I secure by using this program? ####

See the "Limitations" section.

#### Does it compare the actual fingerprint for the trusted keys? ####

No, unfortunately the validation is handled by git and gpg and
trustcheck only compared the short(long) keyid, since only it (and the
name) is displayed by `git log --show-signature`. Therefore it is advisable
to add `keyid-format long` to your `gpg.conf`. When `--setup-gpg-home`
is called this will be configured for you.

#### Does it support path filters? ####

No, but if somebody submits a patch I will include it :)

#### I moved a repository with a separate gpg home to a new location, what should I do? ####

Just rerun `git trustcheck --setup-gpg-home` - it will update the home
location without deleting any data.

#### What else is recommended with this script? ####

Personally I have the following in my git config:

    [alias]
        new = !sh -c 'git log $1@{1}..$1@{0} "$@"'
        logg = log --show-signature
        gpg = !gpg

You can also designate a default key using `gpg config user.signingkey KEYID`
and since git v2.0.0 you can configure it to always sign commits by doing
`gpg config commit.gpgsign true`.

#### It did not work correctly. ####

Please describe the situation and, if possible, send me a toy example.
I will try my best to resolve any problems.

#### I have a comment. ####

Drop me a mail.

#### Ok, I want to help. What can I do? ####

You can:

- spread the word
- tip me in bitcoin: 1GCgYPkM6CuWETW3dD4ondnXTWCXDZLW2P or litecoin: LW85bmvZDn1w7gpeEshSpzzdXGDKqZuXXg
- take a look at the list of TODOs and help with something, I accept patches
- suggest an improvement

## TODOs

- "How does it work?" section
- more documentation
- tests
- setup.py
- better automation of help generation
- debian package
- aur package


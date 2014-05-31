#!/bin/bash
# Script for generating the demo in the README, needs manual work afterwards
# ./demo.sh 2>&1 | grep -v "^+ echo '#" | grep -v "^+ echo$" | sed 's/^+ /$ /' | awk '{print "    "$0}' >> ../README.md

set -e
set -x

# NOTE: this script changes $HOME
    
echo $SCRIPT_DIR

#### functions
function get_key {
    gpg --with-colons --list-keys "$1" | head -n 2 | awk -F : '{print $5}' | tail -n 1
}

function assert {
    grep -q "$@" || exit 1 #bash
}

function gpg_fix_trust {
    gpg --list-keys --with-colons --fingerprint | \
        grep fpr | awk -F : '{print $10 ":6"}' | \
        gpg --import-ownertrust
}

function gpg_fingerprint {
    gpg --list-keys "$1" --with-colons --fingerprint | \
        grep fpr | awk -F : '{print $10}'
}

function generate_gpg_keys {
    mkdir d1 && GNUPGHOME=$PWD/d1 gpg --gen-key --batch "$SCRIPT_DIR"/fixtures/key_gen.txt && GNUPGHOME=$PWD/d1 gpg --export-secret-keys --armor > "$SCRIPT_DIR"/fixtures/gpg_keys.gpg
    mkdir d2 && GNUPGHOME=$PWD/d2 gpg --gen-key --batch "$SCRIPT_DIR"/fixtures/unknown_key_gen.txt && GNUPGHOME=$PWD/d2 gpg --export-secret-keys --armor > "$SCRIPT_DIR"/fixtures/unknown_gpg_keys.gpg
}

#### end functions


#### SETUP
export SCRIPT_DIR="$(readlink -f $(dirname $0))"
rm -rf testground
mkdir -p testground/home2 && cd testground
export TESTGROUND="$PWD"
ln -s "$SCRIPT_DIR"/../git_trustcheck.py git-trustcheck
export PATH="$TESTGROUND":"$PATH"
export HOME="$TESTGROUND"
unset GNUPGHOME

#### setup_git
cat > .gitconfig <<\EOF
[user]
    name = Tester Testerov
    email = tester@example.com
EOF
# repos
mkdir repo && git -C repo init --bare
ORIGIN=$PWD/repo
git clone "file://$ORIGIN" a
git clone "file://$ORIGIN" b

echo "===### setup_gpg ==="
gpg -K 2>/dev/null
( echo "keyid-format long"; echo "no-permission-warning" ) > .gnupg/gpg.conf

echo "===### initialize_gpg_keys ==="
gpg --import "$SCRIPT_DIR"/fixtures/gpg_keys.gpg
GNUPGHOME="$ORIGIN" gpg --import "$SCRIPT_DIR"/fixtures/unknown_gpg_keys.gpg
GNUPGHOME="$ORIGIN" gpg_fix_trust
export KEYA=`get_key TesterA`
export KEYB=`get_key TesterB`
gpg_fix_trust

echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 'msg1_unsigned'
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 'msg2' -S$KEYA
git -C a push origin master
git -C b pull origin master
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'msg3_unsigned'
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'msg4' -S$KEYB
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'msg5_unsigned'
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'msg6_unsigned'
git -C b push origin master

cd a
# DEMO
echo "================================"
echo "### situation"
git pull &>/dev/null && git log --show-signature --pretty='format:%H %s'

echo
echo "### show untrusted in '@{1}..@{0}'"
git trustcheck

echo
echo "### show untrusted in HEAD discarding child trust"
git trustcheck HEAD -c

echo
echo "### add only TesterA to trusted"
git trustcheck -a $KEYA

echo
echo "### show untrusted in '@{1}..@{0}', now TesterB is not trusted"
git trustcheck

echo
echo "### create repo-specific gpg repo"
git trustcheck --setup-gpg-home
git gpg -k
gpg --export-secret-keys $KEYA | git gpg --import
gpg --export-ownertrust | grep $KEYA | git gpg --import-ownertrust
#gpg --yes --batch --delete-secret-keys `gpg_fingerprint $KEYA` && gpg --delete-keys $KEYA
echo a >> a.txt && git add a.txt && git commit -m 'gpg_local' -S$KEYA
echo "# trustcheck ok"
git trustcheck


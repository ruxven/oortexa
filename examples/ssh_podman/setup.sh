#!/bin/bash -e

__MODEL__=""
__URL__=""
__KEY__="none_needed"
__CONTAINER__="worker-node"
__PATH__="."
__HOST__="localhost"
__USER__="$USER"
__PORT__="22"
__IDFILE__="~/.ssh/id_rsa"
use_config=0

if [ -f config.env ]; then
  echo ""
  valid_input=0
  user_input=""
  while [[ valid_input -eq 0 ]]; do
    read -p "Use existing config (y/n)? " user_input
    case $user_input in
      [yY]* )valid_input=1;use_config=1;;
      [nN]* )valid_input=1;use_config=0;;
      * );;
    esac
  done
fi

if [[ use_config -eq 1 ]]; then
  source config.env
else
  echo ""
  read -p "Input model to use for all roles: " __MODEL__
  read -p "Input model endpoint url: " __URL__
  read -p "Input model api key (optional): " __KEY__
  read -p "SSH Host [${__HOST__}]: " user_input && [ -n "$user_input" ] && __HOST__=$user_input
  read -p "SSH User [${__USER__}]: " user_input && [ -n "$user_input" ] && __USER__=$user_input
  read -p "SSH Port [${__PORT__}]: " user_input && [ -n "$user_input" ] && __PORT__=$user_input
  read -p "SSH Identity File [${__IDFILE__}]: " user_input && [ -n "$user_input" ] && __IDFILE__=$user_input
  read -p "Podman container name [${__CONTAINER__}]: " user_input && [ -n "$user_input" ] && __CONTAINER__=$user_input
  read -p "Remote workspace path [${__PATH__}]: " user_input && [ -n "$user_input" ] && __PATH__=$user_input

  {
      echo "export __MODEL__=$__MODEL__"
      echo "export __URL__=$__URL__"
      echo "export __KEY__=$__KEY__"
      echo "export __HOST__=$__HOST__"
      echo "export __USER__=$__USER__"
      echo "export __PORT__=$__PORT__"
      echo "export __IDFILE__=$__IDFILE__"
      echo "export __CONTAINER__=$__CONTAINER__"
      echo "export __PATH__=$__PATH__"
  } > config.env
fi

cat oortexa.yml.base | \
  sed -e "s|__MODEL__|${__MODEL__}|g" | \
  sed -e "s|__URL__|${__URL__}|g" | \
  sed -e "s|__KEY__|${__KEY__}|g" | \
  sed -e "s|__HOST__|${__HOST__}|g" | \
  sed -e "s|__USER__|${__USER__}|g" | \
  sed -e "s|__PORT__|${__PORT__}|g" | \
  sed -e "s|__IDFILE__|${__IDFILE__}|g" | \
  sed -e "s|__PATH__|${__PATH__}|g" | \
  sed -e "s|__CONTAINER__|${__CONTAINER__}|g" > oortexa.yml


valid_input=0
user_input=""
do_scp=0
echo ""
while [[ valid_input -eq 0 ]]; do
  read -p "Copy files to ssh location (y/n)? " user_input
  case $user_input in
    [yY]* )valid_input=1;do_scp=1;;
    [nN]* )valid_input=1;do_scp=0;;
    * );;
  esac
done

if [[ do_scp -eq 1 ]]; then
  echo ""
  echo "Copying files to configured ssh location..."
  IDFILE_ARG=""
  if [ -n "$__IDFILE__" ]; then
    IDFILE_ARG="-i ${__IDFILE__}"
  fi
  ssh \
    $IDFILE_ARG \
    -p ${__PORT__} \
    "${__USER__}@${__HOST__}" "mkdir -p ${__PATH__}" || exit 1
  echo "Copying files to remote ssh location..."
  scp \
    $IDFILE_ARG \
    -P ${__PORT__} \
    ./build.sh \
    "${__USER__}@${__HOST__}:${__PATH__}/."  || exit 1
  echo "Files in remote ssh location:"
  ssh \
    $IDFILE_ARG \
    -p ${__PORT__} \
    "${__USER__}@${__HOST__}" "ls -l ${__PATH__}" || exit 1
fi

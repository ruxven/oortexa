#!/bin/bash -e

__MODEL__=""
__URL__=""
__KEY__="none_needed"
__CONTAINER__=""
__PATH__="/"
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
  valid_input=0
  user_input=""
  while [[ valid_input -eq 0 ]]; do
    read -p "Input model to use for all roles: " user_input
    if [ -n "$user_input" ]; then
      __MODEL__=$user_input
      valid_input=1
    fi
  done

  echo ""
  valid_input=0
  user_input=""
  while [[ valid_input -eq 0 ]]; do
    read -p "Input model endpoint url to use for all roles: " user_input
    if [ -n "$user_input" ]; then
      __URL__=$user_input
      valid_input=1
    fi
  done

  echo ""
  valid_input=0
  user_input=""
  while [[ valid_input -eq 0 ]]; do
    read -p "Input model endpoint key to use for all roles (leave blank if using local model with no key): " user_input
    if [ -n "$user_input" ]; then
      __KEY__=$user_input
      valid_input=1
    else
      valid_input=1
    fi
  done

  echo ""
  read -p "Docker container name: [${__CONTAINER__}]: " user_input
  if [ -n "$user_input" ]; then
    __CONTAINER__=$user_input
  fi

  echo ""
  read -p "Docker workspace path [${__PATH__}]: " user_input
  if [ -n "$user_input" ]; then
    __PATH__=$user_input
  fi

  {
      echo "export __MODEL__=$__MODEL__"
      echo "export __URL__=$__URL__"
      echo "export __KEY__=$__KEY__"
      echo "export __CONTAINER__=$__CONTAINER__"
  } > config.env
fi

cat oortexa.yml.base | \
  sed -e "s|__MODEL__|${__MODEL__}|g" | \
  sed -e "s|__URL__|${__URL__}|g" | \
  sed -e "s|__KEY__|${__KEY__}|g" | \
  sed -e "s|__PATH__|${__PATH__}|g" | \
  sed -e "s|__CONTAINER__|${__CONTAINER__}|g" > oortexa.yml


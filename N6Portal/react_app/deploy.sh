#!/bin/bash
set -e
cd /home/dataman/front

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

echo "Pulling the $BRANCH_NAME branch"
git pull
printf "\n-------\n"
echo "Running yarn install"
yarn
printf "\n-------\n"
echo "Building the application with yarn"
yarn build
printf "\n-------\n"
echo "Reloading the Apache2 server"
sudo /etc/init.d/apache2 reload

printf "\n-------\n"
echo "Success"
echo "Repository changes on $BRANCH_NAME have been pulled."
echo "The application has been installed and the Apache2 server has been reloaded."

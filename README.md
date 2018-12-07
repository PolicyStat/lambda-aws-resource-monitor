## Local environment setup

Requires python 3.6+

1. cp template.env local.env
2. Edit local.env
3. pipenv install
4. pipenv shell

## Push new changes to AWS Lambda

1. pipenv shell
2. zappa update

## Running the code on AWS Lambda

1. pipenv shell
2. zappa invoke monitor.monitor

## Running the code locally

1. pipenv shell
2. python monitor

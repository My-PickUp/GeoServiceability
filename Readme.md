Minimum python version required -- 3.9

create a virtual env using the command

`py -3 -m venv venv`


Activate the environment


make a directory with the name app


git clone the directory


install all the requirements using the command

`pip install -r requirements`


create `.env` file in the same directory as app file and add the following according to your database

`
DATABASE_HOSTNAME = localhost
DATABASE_PORT = 5432
DATABASE_PASSWORD = pass123
DATABASE_NAME = mypickup 
DATABASE_USERNAME = postgres
`


use this command to run 

`uvicorn app.main:app --host 0.0.0.0 --port 80`


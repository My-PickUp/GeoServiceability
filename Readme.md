-Minimum python version required -- 3.9
<br>
<br>
-create a virtual env using the command
<br>
`py -3 -m venv venv`
<br>
<br>
-Activate the environment
<br>
<br>
-make a directory with the name app
<br>
<br>
-git clone the directory
<br>
<br>
-install all the requirements using the command
<br>
`pip install -r requirements`
<br>
<br>
-create `.env` file in the same directory as app file and add the following according to your database
<br>
```
DATABASE_HOSTNAME = localhost 
DATABASE_PORT = 5432
DATABASE_PASSWORD = password
DATABASE_NAME = mypickup 
DATABASE_USERNAME = postgres
```
<br>
<br>

-use this command to run 

`uvicorn app.main:app --host 0.0.0.0 --port 80`


py -3.11 -m venv env
Set-ExecutionPolicy RemoteSigned -Scope Process
env\Scripts\activate

pip install datasets
pip install pymongo
pip install requests
pip install fastapi
pip install "fastapi[standard]"
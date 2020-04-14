from __future__ import print_function
from __future__ import unicode_literals

import sys
import json
from thehive4py.api import TheHiveApi
from thehive4py.query import *
from thehive4py.models import CaseObservable
import boto3
import os

CORRELATION_ID_TOKEN = "DLP-Correlation-ID: "
STATE_FILENAME = "ep.state"
bucket = 'mailparser-parsedmail'
temp_directory = 'temp/'

api = TheHiveApi('http://127.0.0.1:9000', '06rKYFdFSDpDVh0q8/zEPl9+W5ObCMmc')
s3 = boto3.client('s3')


def search_cases(title, query, range, sort):
    
    new_cases = {}
    response = api.find_cases(query=query, range=range, sort=sort)

    #get correlation ids by parsing description
    if response.status_code == 200:
        resp = response.json()
        print("Found " + str(len(resp)) + " new case(s)")
        for r in resp:
            desc = r["description"]
            case_id = r["id"]
            case_no = r["caseId"]
            desc_first_line = desc.partition('\n')[0]
    

            if desc_first_line.find(CORRELATION_ID_TOKEN) == 0:
                correlation_id = desc_first_line[len(CORRELATION_ID_TOKEN):]
            
            new_cases[case_id] = [case_no, correlation_id]
            print("- Case ID " + str(case_id) + " has DLP Correlation ID: " + correlation_id)
    
        
        #print(json.dumps(response.json(), indent=4, sort_keys=True))
        #parsed_json = (json.loads(response.json()))
    else:
        print('ko: {}/{}'.format(response.status_code, response.text))
        sys.exit(0)
    
    #new_cases = {'4' : '15bcd698-2a50-459a-90b0-cb85edd35f8b'}
    return new_cases


def upload_observable(case_no, file_location, file_name):

    file_observable = CaseObservable(dataType='file',
                        data=[file_location],
                        tlp=1,
                        ioc=False,
                        message='uploaded bgit staty evidence puller script'
                        )
    response = api.create_case_observable(case_no, file_observable)
    if response.status_code == 201:
        #print(json.dumps(response.json(), indent=4, sort_keys=True))
        print("Uploaded " + file_location + " to case " + str(case_no))
    else:
        print('ko: {}/{}'.format(response.status_code, response.text))
        sys.exit(0)


f = open(STATE_FILENAME, "r")
file_value = f.readline().strip()
f.close()
last_case_no = int(file_value)  
print("Searching for new DLP cases since case " + str(last_case_no))

# search new dlp cases in TheHive
new_cases = search_cases("Search for new DLP cases", And(Eq('tags', 'dlp'), Gt('caseId', last_case_no)), 'all', [])
#new_cases = search_cases("Search for new DLP cases", Eq('tags', 'dlp'), 'all', [])
    #search("List Amber cases", Eq('tlp', 2), 'all', [])
    #search("List cases having some TLP values", In('tlp', [1, 3]), 'all', ['+tlp'])
    #search("Case of title containing 'TheHive4Py'", String("title:'TheHive4Py'"), 'all', [])
    #search("Closed cases, with tlp greater than or equal to Amber", And(Eq('status', 'Resolved'), Gte('tlp', 2), Gt('severity', 2)), '0-1', [])


for case_id, case_info in new_cases.items():
    case_no = case_info[0]
    correlation_id = case_info[1]
    print("Downloading evidence for " + case_id)

    case_objects = s3.list_objects_v2(Bucket = bucket, Prefix = correlation_id)

    if case_objects:
        contents = case_objects["Contents"]
    
        for c in contents:
            key = c["Key"]
            file_name = key.split("/")[1]

            file_location = temp_directory + file_name
        
            s3.download_file(bucket, key, file_location)
            upload_observable(case_id, file_location, file_name)    
            os.remove(file_location)
    else:
        print("No files found for " + correlation_id)
    
    # should be something more robust such as "cases updated since last scan"
    if(case_no > last_case_no):
        last_case_no = case_no

f = open(STATE_FILENAME, "w")
f.write(str(last_case_no))
f.close()
print("Last case scanned is " + str(last_case_no))

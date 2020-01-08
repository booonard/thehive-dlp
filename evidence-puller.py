from __future__ import print_function
from __future__ import unicode_literals

import sys
import json
from thehive4py.api import TheHiveApi
from thehive4py.query import *
from thehive4py.models import CaseObservable
import boto3
import os

api = TheHiveApi('http://127.0.0.1:9000', '06rKYFdFSDpDVh0q8/zEPl9+W5ObCMmc')
s3 = boto3.client('s3')
CORRELATION_ID_TOKEN = "DLP-Correlation-ID: "
bucket = 'mailparser-parsedmail'
temp_directory = 'temp/'

def search_cases(title, query, range, sort):
    
    print("Searching for new DLP cases...")

    new_cases = {}
    response = api.find_cases(query=query, range=range, sort=sort)

    #get correlation ids by parsing description
    if response.status_code == 200:
        resp = response.json()
        print("Found " + str(len(resp)) + " new case(s)")
        for r in resp:
            desc = r["description"]
            case_no = r["id"]
            desc_first_line = desc.partition('\n')[0]
    

            if desc_first_line.find(CORRELATION_ID_TOKEN) == 0:
                correlation_id = desc_first_line[len(CORRELATION_ID_TOKEN):]
            
            new_cases[case_no] = correlation_id
            print("- Case ID " + str(case_no) + " has DLP Correlation ID: " + correlation_id)
    
        
        #print(json.dumps(response.json(), indent=4, sort_keys=True))
        #parsed_json = (json.loads(response.json()))
    else:
        print('ko: {}/{}'.format(response.status_code, response.text))
        sys.exit(0)
    
    #new_cases = {'4' : '15bcd698-2a50-459a-90b0-cb85edd35f8b'}
    return new_cases


def upload_observable(case_no, file_location, file_name):
    print("Uploading " + file_location + " to case " + str(case_no))

    file_observable = CaseObservable(dataType='file',
                        data=[file_location],
                        tlp=1,
                        ioc=False,
                        message='uploaded by evidence puller script'
                        )
    response = api.create_case_observable(case_no, file_observable)
    if response.status_code == 201:
        #print(json.dumps(response.json(), indent=4, sort_keys=True))
        print('Upload complete')
    else:
        print('ko: {}/{}'.format(response.status_code, response.text))
        sys.exit(0)


# search new dlp cases in TheHive
new_cases = search_cases("Search for new DLP cases", Eq('tags', 'dlp'), 'all', [])
    #search("List Amber cases", Eq('tlp', 2), 'all', [])
    #search("List cases having some TLP values", In('tlp', [1, 3]), 'all', ['+tlp'])
    #search("Case of title containing 'TheHive4Py'", String("title:'TheHive4Py'"), 'all', [])
    #search("Closed cases, with tlp greater than or equal to Amber", And(Eq('status', 'Resolved'), Gte('tlp', 2), Gt('severity', 2)), '0-1', [])


for case_no, correlation_id in new_cases.items():
    print("downloading evidence for " + correlation_id)

    case_objects = s3.list_objects_v2(Bucket = bucket, Prefix = correlation_id)

    if case_objects:
        contents = case_objects["Contents"]
    
        for c in contents:
            key = c["Key"]
            file_name = key.split("/")[1]

            file_location = temp_directory + file_name
        
            s3.download_file(bucket, key, file_location)
            upload_observable(case_no, file_location, file_name)    
            os.remove(file_location)
    else:
        print("No files found for " + correlation_id)

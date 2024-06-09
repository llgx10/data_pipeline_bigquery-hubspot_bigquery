
import traceback
import pytz
import json
import time
import pandas as pd
from pandas import json_normalize
import os
import sys
import numpy as np
import hashlib
from datetime import datetime, timezone
sys.path.append("./")
from config.hubspot.hubspotoop import HubspotAPI
from config.bigquery.bigquery import BigQuery
import pipeline.hubspot_2_bigquery_migration.properties as prop
from config.redash.Redash import Redash
from pipeline.functions.functions import get_object_cursor_date,genegrate_emitted_info,drop_duplicates_by_id,zip_emitted_info,workflow_monitoring
import constants


#global env
object_type="contacts"




def get_archived_contacts():
    try:
        hb=HubspotAPI()
        payload = {
            "properties": [ prop.extract_properties(object_type) ]
            }
        archived_contact=hb.get_archived_objects(object_type,payload)
        return archived_contact
    except Exception as e:
        print("Error in get_archived_companies: ", str(e))
        return None
    
def get_cursor():
    try:
        cursor_date=get_object_cursor_date(object_type)
        print(cursor_date)
        return cursor_date
    except Exception as e:
        print("Error in get_cursor: ", str(e))
        return None

def genegrate_cursor_data(emitted_at,emitted_id):
    try:
        cursor_data=[{
            "emitted_id":f"{emitted_id}",
            "emitted_at":f"{emitted_at}",
            "object":f"{object_type}",
            "cursor_date":f"{emitted_at}"
        }]
        return cursor_data
    except Exception as e:
        print("Error in genegrate_cursor_data: ", str(e))
        return None

def get_recently_modified_contacts(cursor_date):
    try:
        hb=HubspotAPI()
        payload = json.dumps(
            {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "lastmodifieddate",
                                "operator": "GT",
                                "value": f"{cursor_date}"
                            }
                        ]
                    }
                ],
                "limit":100
            }
        )
        recently_modified_contacts=hb._search_records(object_type,payload)
        return recently_modified_contacts
    except Exception as e:
        print("Error in get_recently_modified_contacts: ", str(e))
        return None

def get_detail_recently_modified_contacts(recently_modified_contacts):
    try:
        hb=HubspotAPI()
        id_list= [{"id": item["id"]} for item in recently_modified_contacts]
        recently_modified_contacts=hb.get_object_in_batch(object_type,id_list)
        return recently_modified_contacts
    except Exception as e:
        print("Error in get_detail_recently_modified_contacts: ", str(e))
        return None





@workflow_monitoring
def Hubspot_contacts_to_BigQuery():
    try:
        emitted_at,emitted_id=genegrate_emitted_info()
        cursor_date=get_cursor()


        recently_modified_contacts=get_recently_modified_contacts(cursor_date)
        recently_modified_contacts_detail=get_detail_recently_modified_contacts(recently_modified_contacts)
        bq = BigQuery()
        if len(recently_modified_contacts_detail)>0:
            
            full_contacts_detail = drop_duplicates_by_id(recently_modified_contacts_detail)
            full_contacts_detail=zip_emitted_info(emitted_at,emitted_id,full_contacts_detail)

            archived_contacts=get_archived_contacts()
            archived_contacts=zip_emitted_info(emitted_at,emitted_id,archived_contacts)
            
            contacts_schema_dict=bq.get_table_schema('hubspot','hubspot_contacts')
            hubspot_contacts_bigquery_config = bq.get_table_config('hubspot','hubspot_contacts')
            
            pk = 'id'
            unarchived_cursor='updatedAt'
            archived_cursor='archived'
            
            bq.json_upsert_to_bigquery(full_contacts_detail, hubspot_contacts_bigquery_config, pk, unarchived_cursor,contacts_schema_dict)
            bq.json_upsert_to_bigquery(archived_contacts, hubspot_contacts_bigquery_config, pk, archived_cursor,contacts_schema_dict)
        else:
            print("no new contacts")
        
        
        cursor_data=genegrate_cursor_data(emitted_at,emitted_id)
        cursor_bigquery_config=bq.get_table_config('hubspot','hubspot_object_cursor')
        cursor_schema_dict=bq.get_table_schema('hubspot','hubspot_object_cursor')
        bq.json_append_to_bigquery(cursor_data,cursor_bigquery_config,cursor_schema_dict)
        return len(recently_modified_contacts_detail)
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return 0

    

if __name__ == "__main__":
    Hubspot_contacts_to_BigQuery()
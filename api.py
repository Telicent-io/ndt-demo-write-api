from typing import Union
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict

from fastapi import FastAPI, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import requests
import uuid

jenaURL = os.getenv("JENA_URL", "localhost")
jenaPort = os.getenv("JENA_PORT", "3030")
ontoDataset = os.getenv("ONTO_DATASET", "ontology")
dataset = os.getenv("KNOWLEDGE_DATASET", "knowledge")
default_security_label = os.getenv("DEFAULT_SECURITY_LABEL",'')
data_uri_stub = os.getenv("DATA_URI",'http://telicent.io/data/')

ies = "http://ies.data.gov.uk/ontology/ies4#"
ies_assessed = ies+"assessed"
ies_Assessment = ies+"Assessment"

prefixes = f"""
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ies: <{ies}>
PREFIX tel: <http://telicent.io/ontology/>
PREFIX data: <{data_uri_stub}>
PREFIX ndt: <http://nationaldigitaltwin.gov.uk/ontology#>
"""

class Assessment(BaseModel):
    """
    An assessment
    """
    assessedItem: str """thing"""
    assessmentType: str
    dateOverride: datetime = None
    userOverride: str = None
    uriOverride: str = None
    stateTypeOverride: str = ies+"State"
    stateUriOverride: str = None

class AssessmentClass(BaseModel):
    uri:str
    shortName:str
    superClass:str

app = FastAPI()







assessment_classes = {}

def run_sparql_query(query:str):
    get_uri = "http://"+jenaURL+":"+jenaPort+"/"+ ontoDataset +"/query"
    response = requests.get(get_uri,params={'query':prefixes + query})
    return response.json()

def run_sparql_update(query:str,securityLabel=None):
    if securityLabel == None:
        securityLabel = default_security_label
    post_uri =  "http://"+jenaURL+":"+jenaPort+"/"+ dataset +"/update"
    headers = {
        'Accept': '*/*',
        'Security-Label':securityLabel,
        'Content-Type': 'application/sparql-update'
    }
    requests.post(post_uri,headers=headers,data=prefixes+query)


def shorten(uri):
    out = uri.replace("http://ies.data.gov.uk/ontology/ies4#","ies:")
    out = out.replace("http://nationaldigitaltwin.gov.uk/ontology#","ndt:")
    return out

def get_assessment_subtypes():
    global assessment_classes
    assessment_classes = {}
    assessments = run_sparql_query(f"""
        SELECT ?ass ?parent WHERE 
            {{
                ?ass rdfs:subClassOf* ies:Assessment . 
                ?ass rdfs:subClassOf ?parent
            }}""")
    out = []
    if assessments and assessments['results'] and assessments['results']['bindings']:
        for ass in assessments['results']['bindings']:
            out.append({"uri":ass['ass']['value'],"shortName":shorten(ass['ass']['value']),"superClass":ass['parent']['value']})
            assessment_classes[ass['ass']['value']]= {"uri":ass['ass']['value'],"shortName":shorten(ass['ass']['value']),"superClass":ass['parent']['value']}
    return out


@app.get("/")
def read_root():
    return "NDT-DEMO"

@app.get("/assessment-classes", response_model=List[AssessmentClass])
def get_assessments():
    return get_assessment_subtypes()

@app.post("/assessments")
def post_assessment(ass: Assessment):
    if ass.assessedItem == None or ass.assessedItem == "":
        raise HTTPException(status_code=400, detail="No assessed object provided")
    if ass.assessmentType == None or ass.assessmentType == "":
        raise HTTPException(status_code=400, detail="No assessment class provided")
    if ass.assessmentType not in assessment_classes:
        get_assessment_subtypes()
        if ass.assessmentType not in assessment_classes:
            raise HTTPException(status_code=404, detail="Assessment Class: " + ass.assessmentType + " not found")
        else:
            if ass.userOverride:
                user = ass.userOverride
            else:
                user = data_uri_stub+"JaneDoe" #DON'T KNOW HOW TO GET THE USER ID
            if ass.dateOverride:
                date = ass.dateOverride
            else:
                date = today = datetime.now()
            date_uri = "http://iso.org/iso8601#"+date.isoformat().replace(" ","T")
            if ass.uriOverride == None or ass.uriOverride == "":
                uri = data_uri_stub+str(uuid.uuid4())
            else:
                uri = ass.uriOverride
            query = f'''INSERT DATA 
            {{
                <
                <{uri}> a <{ass.assessmentType}>  . 
                <{uri}> ies:assessed <{ass.assessedItem}> .
                <{uri}> ies:assessor <{user}> .
            }}'''
            print(query)
            run_sparql_update(query=query)

            return uri
    raise HTTPException(status_code=400, detail="Could not create assessment")    

#if __name__ == "__main__":
#    uvicorn.run(app, host="0.0.0.0", port=int(5021),reload=app)
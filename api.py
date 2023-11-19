from typing import Union
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Dict

from fastapi import FastAPI, Request, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import requests
import uuid


#If you're running this yourself, and the Jena instance you're using is not local, you can used environment variables to override
jenaURL = os.getenv("JENA_URL", "localhost")
jenaPort = os.getenv("JENA_PORT", "3030")
ontoDataset = os.getenv("ONTO_DATASET", "ontology")
dataset = os.getenv("KNOWLEDGE_DATASET", "knowledge")
default_security_label = os.getenv("DEFAULT_SECURITY_LABEL",'')
data_uri_stub = os.getenv("DATA_URI",'http://telicent.io/data/') #This can be overridden in use

#The URIs used in the ontologies
ies = "http://ies.data.gov.uk/ontology/ies4#"
ndt="http://nationaldigitaltwin.gov.uk/ontology#"

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

class IesThing(BaseModel):
    """
    The top of the class tree
        uri - the uri of the created data object
    """
    uri:str = None 

class IesAssessment(IesThing):
    """
    An IES assessment - not used at this stage - please use IesAssessToBeTrue
    """
    assessedItem: str 
    assessor: str
    assessmentType: str = None
    inPeriod: date = None

class IesAssessToBeTrue(IesAssessment):
    """
    An IES assessment used to validate a statement or state
    """
    assessmentType: str = ies+"AssessToBeTrue"

class IesClass(IesThing):
    """
    An IES class (types of things) from the IES ontology, or from local extensions such as the NDT ontology extensions
    """
    shortName:str
    superClasses:List[str] = []
    description:List[str] = []

class IesState(IesThing):
    """
    A temporal stage of an element in IES - we use this here to identify the validity period of a building for the assessment being made
    """
    stateType:str
    stateOf: str
    startDateTime: datetime = None
    endDateTime: datetime = None

class IesAccount(IesThing):
    """
    Not used at this stage
    """
    id:str
    name:str = None
    email:str = None

class IesPerson(IesThing):
    """
    A person - in this case of this API, this is the person who conducted the assessment
    """
    surname:str
    givenName:str


#Checks to see if an iesThing has a URI - if not, it mints a new uri using the data_uri_stub
def mint_uri(item:IesThing):
    if item.uri == None:
        item.uri = data_uri_stub+str(uuid.uuid4())
    return item



description = """
The NDT Assessment Write-Back API was developed to provide NDT users a strictly controlled way to create new data in a Telicent CORE deployment.

The data creation is centred around states of buildings and the IES Assessment event.

# Local Installation

If you want to run this locally, you'll need to:

* install Apache Jena Fuseki - https://jena.apache.org/download/index.cgi
* run Apache Jena Fuseki
* create two datasets in Fuseki - ONTOLOGY and KNOWLEDGE
* load the ttl files in this repo into the ONTOLOGY dataset (again, use the Fuseki UI) - this will provide the API with access to the ontologies
* pip install all the modules listed in requirements.txt
* run the api.py file (Python 3.9 or later)

# Getting Started

The first thing to do is to request which building state classes are available - call the /buildings/states/classes endpoint. That will return a list of class objects - e.g. 

    [
        {
            "uri": "http://nationaldigitaltwin.gov.uk/ontology#BuildingState",
            "shortName": "ndt:BuildingState",
            "superClasses": [
                "http://ies.data.gov.uk/ontology/ies4#LocationState"
            ],
            "description": []
        },
        {
            "uri": "http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOfA",
            "shortName": "http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOfA",
            "superClasses": [
                "http://nationaldigitaltwin.gov.uk/ontology#BuildingState"
            ],
            "description": []
        },
        {
            "uri": "http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOfB",
            "shortName": "http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOfB",
            "superClasses": [
                "http://nationaldigitaltwin.gov.uk/ontology#BuildingState"
            ],
            "description": []
        }
    ]

You will also need to create a new Person (or have the URI of an existing one). To create a new Person, POST to the /people endpoint with a payload such as:

    {
        "givenName" : "Anne",
        "surname" : "Smith"
    }

The endpoint will return the URI for the new Person instance (you can also provide your own URI if you want to set a specific one). In this example, let's say it returned a uri of:

    http://telicent.io/data/d6cfb50d-c72c-40a8-a5e9-5b5a717aa730



You then need to create a new state instance, and apply it to the building. That means posting an iesState object to the /buildings/states endpoint. An example would be:

    {
        "uri":"http://myItem.com/my_building_state_1",
        "stateOf":"http://myItem.com/my_building",
        "stateType":"http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOfD",
        "startDateTime":"2023-11-17T09:00:00",
        "endDateTime":"2023-11-17T17:00:00"
    }

The start and end datetimes specify the temporal extent of the state (if known...if not, you can leave them blank). The stateOf property refers to the URI of the building. The stateType should be one of the classes returned by the /buildings/states/classes endpoint

You can also optionally provide a uri property for the state. If no uri is provided, one will be minted, and returned in the http response body.

All that remains after that is to put some assessment information into the system, by posting to the /assessments/assess-to-be-true endpoint:

    {
        "assessedItem":"http://myItem.com/my_building_state_1",
        "assessor":"http://telicent.io/data/d6cfb50d-c72c-40a8-a5e9-5b5a717aa730",
        "inPeriod":"2023-11-19"
    }

The assessedItem and assessor are the URIs we've already produced for the state and the person. The inPeriod property is the date of the assessment in ISO8601 format. If you don't provide the inPeriod property, the API will just use today's date.

"""

app = FastAPI(title="NDT Assessment Write-Back API",
              description=description,
              license_info={
                    "name": "Apache 2.0",
                    "url": "https://www.apache.org/licenses/LICENSE-2.0.html"
            })

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



assessment_classes = {}
building_state_classes = {}

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


def get_subtypes(super_class,exclude_super = None):
    sub_classes = {}
    sub_list = []
    if exclude_super != None and exclude_super != "":
        filter_clause = f"""FILTER NOT EXISTS {{ ?sub rdfs:subClassOf* <{exclude_super}>  }}  """
    else:
        filter_clause = """"""
    results = run_sparql_query(f"""
        SELECT ?sub ?parent ?comment WHERE 
            {{
                ?sub rdfs:subClassOf* <{super_class}> . 
                ?sub rdfs:subClassOf ?parent .
                OPTIONAL {{ ?sub rdfs:comment ?comment}}
                {filter_clause}
            }}""")

    if results and results['results'] and results['results']['bindings']:
        for sub in results['results']['bindings']:
            sub_uri=sub['sub']['value']
            if sub['sub']['value'] not in assessment_classes:
                #create a new empty(ish) item
                my_obj = {"uri":sub_uri,"shortName":shorten(sub_uri),"superClasses":[],"description":[]}
                sub_classes[sub_uri]= my_obj
            else:
                my_obj = sub_classes[sub_uri]
            #If there are any comments, append them
            if "comment" in sub and sub['comment']['value'] not in assessment_classes[sub['sub']['value']]["description"]:
                assessment_classes[sub['sub']['value']]["description"].append(sub['comment']['value'])
            #There may be more than one parent, so append them as we find them
            if sub['parent']['value'] not in my_obj["superClasses"]:
                    my_obj["superClasses"].append(sub['parent']['value'])

    sub_list = []
    for key in sub_classes:
        sub = sub_classes[key]
        sub_list.append({"uri":key,"shortName":sub["shortName"],"superClasses":sub["superClasses"],description:sub["description"]})
    
    return sub_classes, sub_list


@app.get("/")
def read_root():
    return "NDT-DEMO"

@app.get("/assessment-classes", response_model=List[IesClass])
def get_assessments():
    sub_classes, sub_list = get_subtypes(ies+"Assessment")
    global assessment_classes
    assessment_classes = sub_classes
    return sub_list

@app.get("/buildings/states/classes", response_model=List[IesClass])
def get_building_states():
    sub_classes, sub_list = get_subtypes(ndt+"BuildingState",exclude_super=ies+"Location")
    global building_state_classes_classes
    building_state_classes_classes = sub_classes
    return sub_list

@app.post("/people")
def post_building_state(per: IesPerson):
    mint_uri(per)
    query = f'''INSERT DATA 
            {{
                <{per.uri}> a ies:Person .
                <{per.uri}> ies:hasName <{per.uri+"_NAME"}> .
                <{per.uri+"_NAME"}> a ies:PersonName .
                <{per.uri+"_SURNAME"}> a ies:Surname .
                <{per.uri+"_SURNAME"}> ies:inRepresentation <{per.uri+"_NAME"}> .
                <{per.uri+"_SURNAME"}> ies:representationValue "{per.surname}" .
                <{per.uri+"_GIVENNAME"}> a ies:GivenName .
                <{per.uri+"_GIVENNAME"}> ies:inRepresentation <{per.uri+"_NAME"}> .
                <{per.uri+"_GIVENNAME"}> ies:representationValue "{per.givenName}" .
            }}'''
    print(query)
    run_sparql_update(query=query)
    return per.uri

@app.post("/buildings/states")
def post_building_state(bs: IesState):
    mint_uri(bs)
    if bs.startDateTime:
        start_date = "http://iso.org/iso8601#"+bs.startDateTime.isoformat().replace(" ","T")
        start_sparql = f"""
                <{bs.uri}_start> a ies:BoundingState .
                <{bs.uri}_start> ies:isStartOf <{bs.uri}> .
                <{bs.uri}_start> ies:inPeriod <{start_date}> .
        """
    else:
        start_sparql = """"""

    if bs.endDateTime:
        end_date = "http://iso.org/iso8601#"+bs.startDateTime.isoformat().replace(" ","T")
        end_sparql = f"""
                <{bs.uri}_end> a ies:BoundingState .
                <{bs.uri}_end> ies:isEndOf <{bs.uri}> .
                <{bs.uri}_end> ies:inPeriod <{end_date}> .
        """
    else:
        end_sparql = """"""

    end_date = "http://iso.org/iso8601#"+bs.endDateTime.isoformat().replace(" ","T")
    query = f'''INSERT DATA 
            {{
                <{bs.uri}> a <{bs.stateType}> .
                <{bs.uri}> ies:isStateOf <{bs.stateOf}> .
                {start_sparql}
                {end_sparql}
            }}'''
    print(query)
    run_sparql_update(query=query)
    return bs.uri

@app.post("/accounts")
def post_account(acc: IesAccount):
    if acc.uri == None:
        acc.uri = data_uri_stub+"Account-"+acc.id
    if acc.email != None:
            email_sparql = f"""
            <{acc.uri+"email"}> a ies:EmailAddress .
            <{acc.uri+"email"}> ies:representationValue "{acc.email}" .
            <{acc.uri}> ies:isIdentifiedBy <{acc.uri+"email"}> .
        """
    else:
        email_sparql = """"""

    if acc.name != None:
            name_sparql = f"""
            <{acc.uri+"name"}> a ies:Name .
            <{acc.uri+"name"}> ies:representationValue "{acc.name}" .
            <{acc.uri}> ies:hasName <{acc.uri+"name"}> .
        """
    else:
        name_sparql = """"""

    query = f'''INSERT DATA 
        {{
            <{acc.uri}> a ies:Account .
            <{acc.uri+"ID"}> a ies:AccountNumber .
            <{acc.uri+"ID"}> ies:representationValue "{acc.id}" .
            <{acc.uri}> ies:isIdentifiedBy <{acc.uri+"ID"}> .
            {email_sparql}
            {name_sparql}
        }}'''
    print(query)
    run_sparql_update(query=query)
    return acc.uri

@app.post("/assessments/assess-to-be-true")
def post_assess_to_be_true(ass: IesAssessToBeTrue):
    mint_uri(ass)
    if ass.inPeriod == None:
        ass.inPeriod = datetime.today().strftime('%Y-%m-%d')
    query = f'''INSERT DATA 
            {{
                <{ass.uri}> a <{ass.assessmentType}> .
                <{ass.uri}> ies:assessed <{ass.assessedItem}> .
                <{ass.uri}> ies:assessor <{ass.assessor}> .
                <{ass.uri}> ies:inPeriod "{ass.inPeriod}"
            }}'''
    run_sparql_update(query=query)

    return ass.uri

@app.post("/uri-stub",
          description="Sets the default uri stub used by the API when generating data uris - it will append a UUID to the stub for every URI it creates")
def post_uri_stub(uri:str):
    data_uri_stub = uri
    return data_uri_stub

@app.post("/assessments")
def post_assessment(ass: IesAssessment, req:Request):
    mint_uri(ass)
    state_uri = ""
    start_state=""
    end_state=""
    state_type = ""
    if ass.assessedItem == None or ass.assessedItem == "":
        raise HTTPException(status_code=400, detail="No assessed object provided")
    if ass.assessmentType == None or ass.assessmentType == "":
        raise HTTPException(status_code=400, detail="No assessment class provided")
    if ass.assessmentType not in assessment_classes:
        get_assessments()
        if ass.assessmentType not in assessment_classes:
            raise HTTPException(status_code=404, detail="Assessment Class: " + ass.assessmentType + " not found")
        else:
            if ass.userOverride:
                user = ass.userOverride
            else:
                user = data_uri_stub+"JaneDoe" #DON'T KNOW HOW TO GET THE USER ID

            start_date = "http://iso.org/iso8601#"+ass.startDate.isoformat().replace(" ","T")
            end_date = "http://iso.org/iso8601#"+ass.endDate.isoformat().replace(" ","T")
            query = f'''INSERT DATA 
            {{
                <{state_uri}> a <{state_type}> .
                <{state_uri}> ies:isStateOf <{ass.assessedItem}>
                <{start_state}> a ies:BoundingState .
                <{start_state}> ies:isStartOf <{state_uri}> .
                <{start_state}> ies:inPeriod <{start_date}> .
                <{end_state}> a ies:BoundingState .
                <{end_state}> ies:isEndOf <{state_uri}> .
                <{end_state}> ies:inPeriod <{end_date}> .
                <{ass.uri}> a <{ass.assessmentType}>  . 
                <{ass.uri}> ies:assessed <{state_uri}> .
                <{ass.uri}> ies:assessor <{user}> .
            }}'''
            print(query)
            run_sparql_update(query=query)

            return ass.uri
    raise HTTPException(status_code=400, detail="Could not create assessment")    

#if __name__ == "__main__":
#    uvicorn.run(app, host="0.0.0.0", port=int(5021),reload=app)
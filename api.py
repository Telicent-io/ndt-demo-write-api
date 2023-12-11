from typing import Union, Optional
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Dict

from fastapi import FastAPI, Request, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import requests
import uuid
import pygeohash as pgh

from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer
from rdflib import Graph, URIRef, Literal, XSD, Namespace

#If you're running this yourself, and the Jena instance you're using is not local, you can used environment variables to override
jenaURL = os.getenv("JENA_URL", "localhost")
jenaPort = os.getenv("JENA_PORT", "3030")
ontoDataset = os.getenv("ONTO_DATASET", "ontology")
dataset = os.getenv("KNOWLEDGE_DATASET", "knowledge")
default_security_label = os.getenv("DEFAULT_SECURITY_LABEL",'')
data_uri_stub = os.getenv("DATA_URI",'http://nationaldigitaltwin.gov.uk/data#') #This can be overridden in use
update_mode = os.getenv("UPDATE_MODE","KAFKA")

#The URIs used in the ontologies
ies = "http://ies.data.gov.uk/ontology/ies4#"
ndt_ont="http://nationaldigitaltwin.gov.uk/ontology#"



def add_prefix(prefix,uri):
    prefix_dict[prefix] = uri

def format_prefixes():
    prefixes = ''
    for prefix in prefix_dict:
        prefixes = prefixes + "PREFIX "+prefix+": <"+prefix_dict[prefix]+">\n"
    return prefixes

prefix_dict = {}
add_prefix("xsd","http://www.w3.org/2001/XMLSchema#")
add_prefix("dc","http://purl.org/dc/elements/1.1/")
add_prefix("rdf","http://www.w3.org/1999/02/22-rdf-syntax-ns#")
add_prefix("rdfs","http://www.w3.org/2000/01/rdf-schema#")
add_prefix("owl","http://www.w3.org/2002/07/owl#")
add_prefix("telicent","http://telicent.io/ontology/")
add_prefix("ies",ies)
add_prefix("data",data_uri_stub)
add_prefix("ndt_ont",ndt_ont)
add_prefix("ndt","http://nationaldigitaltwin.gov.uk/data#")
add_prefix("gp","https://www.geoplace.co.uk/addresses-streets/location-data/the-uprn#")
add_prefix("epc","http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#")


def shorten(uri):
    for prefix in prefix_dict:
        stub = prefix_dict[prefix]
        uri = uri.replace(stub,prefix+":")
    return uri

def lengthen(uri):
    for prefix in prefix_dict:
        stub = prefix_dict[prefix]
        uri = uri.replace(prefix+":",stub)
    return uri

prefixes = format_prefixes()

#Test person is created so we can assign assessments to someone. Once access to user info is available, this will be replaced with the logged in user. i.e. this is just a temporary fix for testing purposes.
test_person_uri = data_uri_stub+"TestUser"

class IesThing(BaseModel):
    """
    The top of the class tree
        uri - the uri of the created data object
    """
    uri:str = None 
    securityLabel: Optional[str] = None
    types:List[str] = []

class IesElement(IesThing):
    inPeriod: date = None
    pass

class IesEntity(IesElement):
    pass

class IesAssessment(IesThing):
    """
    An IES assessment - not used at this stage - please use IesAssessToBeTrue
    """
    assessedItem: str 
    assessor: str
    assessmentType: str = None

class IesAssessToBeTrue(IesAssessment):
    """
    An assessment used to validate a statement or state
    """
    types: List[str] = [ies+"AssessToBeTrue"]

class IesAssessToBeFalse(IesAssessment):
    """
    An IES assessment used to validate a statement or state
    """
    types: List[str] = [ies+"AssessToBeFalse"]

class IesClass(IesThing):
    """
    An IES class (types of things) from the IES ontology, or from local extensions such as the NDT ontology extensions
    """
    shortName:str
    superClasses:List[str] = []
    description:List[str] = []

class IesState(IesElement):
    """
    A temporal stage of an element in IES - we use this here to identify the validity period of a building for the assessment being made
    """
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

class Building(IesThing):
    uprn: str = None
    currentEnergyRating: str = None
    types:List[str] = []
    parentBuildingTOID:str = None
    buildingTOID:str = None
    parentBuilding:str = None
    flags:Dict = {}


class IesEntityAndStates(BaseModel):
    entity:IesEntity
    states:List[IesState]

#Checks to see if an iesThing has a URI - if not, it mints a new uri using the data_uri_stub
#Also checks if a security label has been set
def mint_uri(item:IesThing):
    if item.uri == None:
        item.uri = data_uri_stub+str(uuid.uuid4())
    if item.securityLabel == None:
        item.securityLabel = default_security_label
    return item

with open('README.md', 'r') as file:
    description = file.read()


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


#Local dictionaries that are used to check that certain classes exist before posting references to them
assessment_classes = {}
building_state_classes = {}

def run_sparql_query(query:str,query_dataset=dataset):
    get_uri = "http://"+jenaURL+":"+jenaPort+"/"+ query_dataset +"/query"
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
            }}""",query_dataset=ontoDataset)

    if results and results['results'] and results['results']['bindings']:
        for sub in results['results']['bindings']:
            sub_uri=sub['sub']['value']
            if sub_uri not in sub_classes:
                #create a new empty(ish) item
                my_obj = {"uri":sub_uri,"shortName":shorten(sub_uri),"superClasses":[],"description":[]}
                sub_classes[sub_uri]= my_obj
            else:
                my_obj = sub_classes[sub_uri]
            #If there are any comments, append them
            if "comment" in sub and sub['comment']['value'] not in sub_classes[sub['sub']['value']]["description"]:
                sub_classes[sub_uri]["description"].append(sub['comment']['value'])
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

@app.get("/assessment-classes", response_model=List[IesClass],description="returns all the subclasses of ies:Assessment that are in the ontology")
def get_assessments():
    sub_classes, sub_list = get_subtypes(ies+"Assessment")
    global assessment_classes
    assessment_classes = sub_classes
    return sub_list

@app.get("/buildings/states/classes", response_model=List[IesClass],description="returns all the subclasses of BuildingState that are in the ontology")
def get_building_state_classes():
    sub_classes, sub_list = get_subtypes(ndt_ont+"BuildingState",exclude_super=ies+"Location")
    global building_state_classes
    building_state_classes = sub_classes
    return sub_list


@app.post("/people",description="Creates a new Person")
def post_person(per: IesPerson):
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
    run_sparql_update(query=query,securityLabel=per.securityLabel)
    return per.uri

@app.get("/buildings",response_model=List[Building],description="Gets all the buildings inside a geohash (min 5 digits) along with their types, TOIDs, UPRNs, and current energy ratings")
def get_buildings_in_geohash(geohash:str):
    if len(geohash) < 5:
        raise HTTPException(422,detail="Lat Lon range too wide, please provide at least five digits")  
    gh = "http://geohash.org/"+geohash
   
    query = f"""
        SELECT
            ?building
            ?uprn_id
            ?building_toid_id
            ?parent_building_toid_id
            ?current_energy_rating
            ?parent_building
            ?type
            ?flag
            ?flag_type
            ?flag_person
            ?flag_date
            ?flag_assessment
            ?flag_ass_date
            ?flag_assessor
        WHERE {{
            ?building ies:inLocation ?geopoint .
            BIND(str(?geopoint) as ?gh) .
            FILTER (STRSTARTS(?gh,"{gh}") )
            ?building a ?type .

            ?state ies:isStateOf ?building .
            ?state a ?energy_rating .
            BIND(REPLACE(str(?energy_rating),"http://gov.uk/government/organisations/department-for-levelling-up-housing-and-communities/ontology/epc#BuildingWithEnergyRatingOf","","i") as ?current_energy_rating)
    
            ?building ies:isIdentifiedBy ?uprn .
            ?uprn ies:representationValue ?uprn_id .
            ?uprn rdf:type gp:UniquePropertyReferenceNumber .
    
            OPTIONAL {{
                ?flag ies:interestedIn ?building .
                ?flag ies:isStateOf ?flag_person .
                ?flag a ?flag_type . 
                ?flag ies:inPeriod ?flag_date .
                OPTIONAL {{
                    ?flag_assessment ies:assessed ?flag .
                    ?flag_assessment ies:inPeriod ?flag_ass_date .
                    ?flag_assessment ies:assessor ?flag_assessor .
                }}
            }}
    
            OPTIONAL {{
                ?building ies:isIdentifiedBy ?building_toid .
                ?building_toid rdf:type ies:TOID .
                ?building_toid ies:representationValue ?building_toid_id .
            }}
            OPTIONAL {{
                ?building ies:isPartOf ?parent_building .
                ?parent_building ies:isIdentifiedBy ?parent_building_toid .
                ?parent_building_toid ies:representationValue ?parent_building_toid_id .
                ?parent_building_toid rdf:type ies:TOID .
            }}
    
        }}
    """

    out = {}
    out_array = []
    results = run_sparql_query(query)

    if results and results['results'] and results['results']['bindings']:
        for result in results['results']['bindings']:
            building = shorten(result["building"]["value"])
            typ = shorten(result["type"]["value"])
            if building in out:
                building_obj = out[building]
                if typ not in building_obj["types"]:
                    building_obj["types"].append(typ)
            else:
                energy_rating = result["current_energy_rating"]["value"]
                building_obj = {"uri":building,"uprn":result["uprn_id"]["value"],"currentEnergyRating":energy_rating,"types":[typ],"flags":{},"invalidatedFlags":[]}
                out[building] = building_obj
                out_array.append(building_obj)

            if "flag" in result:
                flag = shorten(result["flag"]["value"])
                if not flag in building_obj["flags"]:
                    flag_obj = {"flagType":shorten(result["flag_type"]["value"]),"flaggedBy":result["flag_person"]["value"],"date":result["flag_date"]["value"]}
                    building_obj["flags"][flag] = flag_obj
                else:
                    flag_obj = building_obj["flags"][flag]
                if "flag_assessment" in result:
                    flag_obj["invalidated"] = result["flag_ass_date"]["value"]
                    flag_obj["invalidatedBy"] = result["flag_assessor"]["value"]

            if "building_toid_id" in result:
                building_obj["buildingTOID"] = result["building_toid_id"]["value"]
            elif "parent_building_toid_id" in result:
                building_obj["parentBuildingTOID"] = result["parent_building_toid_id"]["value"]
            
    return out_array

@app.post("/invalidate-flag",description="Post to this endpoint to invalidate an existing flag.")
def invalidate_flag(request:Request,flagUri:str,assessmentTypeOverride:str=prefix_dict["ndt_ont"]+"AssessToBeFalse",securityLabel = default_security_label):
    assessor = test_person_uri
    assessment_time = "http://iso.org/iso8601#"+datetime.now().isoformat()
    assessment = data_uri_stub+str(uuid.uuid4())
    (ass_subclasses,ass_list) = get_subtypes(ies+"Assess")
    print(ass_subclasses)
    if assessmentTypeOverride not in ass_subclasses:
        raise HTTPException(422,"assessmentTypeOverride must be a subclass of ies:Assess")
    query = f"""
        INSERT DATA {{
            <{assessment}> a <{assessmentTypeOverride}> .
            <{assessment}> ies:assessor <{assessor}> .
            <{assessment}> ies:assessed <{lengthen(flagUri)}> .
            <{assessment}> ies:inPeriod <{assessment_time}> .
        }}
    """
    run_sparql_update(query=query,securityLabel=securityLabel)
    return assessment

@app.get("/buildings/{uprn}", response_model=IesEntityAndStates,description="returns the building that corresponds to the provided UPRN")
def get_building_by_uprn(uprn:str):
    query = f'''SELECT ?building ?buildingType ?state ?stateType WHERE 
                {{
                    ?building ies:isIdentifiedBy ?uprnID .
                    ?building rdf:type ?buildingType .
                    ?uprnID ies:representationValue "{uprn}" .
                    OPTIONAL {{
                        ?state ies:isStateOf ?building .
                        ?state rdf:type ?stateType .
                    }}
                }}
            '''
    results = run_sparql_query(query)
    building = {
        "uri":"",
        "types":[],
    }
    states = {}
    if results and results['results'] and results['results']['bindings']:
        for result in results['results']['bindings']:
            building["uri"] = result["building"]["value"]
            if result["buildingType"]["value"] not in building["types"]:
                building["types"].append(result["buildingType"]["value"])
            if result["state"]["value"]:
                state = result["state"]["value"]
                stateType = result["stateType"]["value"]
                if state not in states:
                    states[state] = {"uri":state,"types":[],"stateOf": building["uri"]}
                if stateType not in states[state]["types"]:
                    states[state]["types"].append(stateType)
    out = {
        "entity":building,
        "states":[]
    }
    for state in states:
        out["states"].append(states[state])
    return out

@app.post("/flag-to-visit",description="Add a flag to an Entity instance as being worth visiting - URI of Entity must be provided")
def post_flag_visit(request:Request,visited:IesEntity):
    if not visited or not visited.uri:
        raise HTTPException(422,"URI of flagged entity must be provided")
    flagger = test_person_uri
    flag_time = "http://iso.org/iso8601#"+datetime.now().isoformat()
    flag_state = data_uri_stub+str(uuid.uuid4())
    query = f"""
        INSERT DATA {{
            <{flag_state}> ies:interestedIn <{visited.uri}> .
            <{flag_state}> ies:isStateOf <{flagger}> .
            <{flag_state}> ies:inPeriod <{flag_time}> .
            <{flag_state}> a ndt:InterestedInVisiting .
        }}
    """
    run_sparql_update(query=query,securityLabel=visited.securityLabel)
    return flag_state

@app.post("/flag-to-investigate",description="Add a flag to an Entity instance as being worth investigating- URI of Entity must be provided")
def post_flag_visit(request:Request,visited:IesEntity):
    if not visited or not visited.uri:
        raise HTTPException(422,"URI of flagged entity must be provided")
    flagger = test_person_uri
    flag_time = "http://iso.org/iso8601#"+datetime.now().isoformat()
    flag_state = data_uri_stub+str(uuid.uuid4())
    query = f"""
        INSERT DATA {{
            <{flag_state}> ies:interestedIn <{visited.uri}> .
            <{flag_state}> ies:isStateOf <{flagger}> .
            <{flag_state}> ies:inPeriod <{flag_time}> .
            <{flag_state}> a ndt:InterestedInInvestigating .
        }}
    """
    run_sparql_update(query=query,securityLabel=visited.securityLabel)
    return flag_state

#@app.post("/buildings/states",description="Add a new state to a building")
def post_building_state(bs: IesState):
    if bs.stateType not in building_state_classes:
        get_building_states()
        if bs.stateType not in building_state_classes:
            raise HTTPException(status_code=404, detail="Building State Class: " + bs.stateType + " not found")
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
    run_sparql_update(query=query,securityLabel=bs.securityLabel)
    return bs.uri

#@app.post("/accounts")
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
    run_sparql_update(query=query,securityLabel=acc.securityLabel)
    return acc.uri

def assess(ass:IesAssessment):
    mint_uri(ass)
    if ass.inPeriod == None:
        ass.inPeriod = datetime.datetime.now().isoformat()
    if ass.assessor == None:
        ass.assessor = test_person_uri

    type_str = ""
    for typ in ass.types:
        type_str = type_str + f'<{ass.uri}> a <{typ}> . ' 
    query = f'''INSERT DATA 
            {{
                {type_str}
                <{ass.uri}> ies:assessed <{ass.assessedItem}> .
                <{ass.uri}> ies:assessor <{ass.assessor}> .
                <{ass.uri}> ies:inPeriod "{ass.inPeriod}"
            }}'''
    run_sparql_update(query=query,securityLabel=ass.securityLabel)

    return ass.uri

#@app.post("/assessments/assess-to-be-true")
def post_assess_to_be_true(ass:IesAssessToBeTrue):
    mint_uri(ass)
    if ass.inPeriod == None:
        ass.inPeriod = datetime.datetime.now().isoformat()
    if ass.assessor == None:
        ass.assessor = test_person_uri
    query = f'''INSERT DATA 
            {{
                <{ass.uri}> a <{ass.types[0]}> .
                <{ass.uri}> ies:assessed <{ass.assessedItem}> .
                <{ass.uri}> ies:assessor <{ass.assessor}> .
                <{ass.uri}> ies:inPeriod "{ass.inPeriod}"
            }}'''
    run_sparql_update(query=query,securityLabel=ass.securityLabel)

    return ass.uri
 
#@app.post("/assessments/assess-to-be-false")
def post_assess_to_be_false(ass:IesAssessToBeFalse):
    mint_uri(ass)
    if ass.inPeriod == None:
        ass.inPeriod = datetime.datetime.now().isoformat()
    if ass.assessor == None:
        ass.assessor = test_person_uri
    query = f'''INSERT DATA 
            {{
                <{ass.uri}> a <{ass.types[0]}> .
                <{ass.uri}> ies:assessed <{ass.assessedItem}> .
                <{ass.uri}> ies:assessor <{ass.assessor}> .
                <{ass.uri}> ies:inPeriod "{ass.inPeriod}"
            }}'''
    run_sparql_update(query=query,securityLabel=ass.securityLabel)

    return ass.uri

@app.post("/uri-stub",
          description="Sets the default uri stub used by the API when generating data uris - it will append a UUID to the stub for every URI it creates")
def post_uri_stub(uri:str):
    data_uri_stub = uri
    return data_uri_stub

@app.get("/uri-stub",
          description="Gets the  default uri stub used by the API when generating data uris")
def get_uri_stub():
    return data_uri_stub

@app.post("/default-security-label",
          description="Sets the default security label used when writing data")
def post_default_security_label(label:str):
    default_security_label = label
    return default_security_label

@app.get("/default-security-label",
          description="Gets the default security label used when writing data")
def get_default_security_label():
    return default_security_label

#@app.post("/assessments")
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
            run_sparql_update(query=query,securityLabel=ass.securityLabel)

            return ass.uri
    raise HTTPException(status_code=400, detail="Could not create assessment")    

#Create a temporary person for this demo...until we can do something else...
person = IesPerson(uri=test_person_uri,givenName = "Test",surname = "User")
post_person(person)



#if __name__ == "__main__":
#    uvicorn.run(app, host="0.0.0.0", port=int(5021),reload=app)
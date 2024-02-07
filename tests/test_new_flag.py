
from unittest import TestCase, mock
import os
os.environ['UPDATE_MODE'] = "FILE"
import api
from api import format_prefixes
from access import AccessClient
from fastapi.testclient import TestClient
from rdflib import Graph, URIRef, Literal
from json import loads
# class IesThing(BaseModel):
#     """
#     The top of the class tree
#         uri - the uri of the created data object
#     """
#     uri:str = None 
#     securityLabel: EDH = None
#     types:List[str] = []
test_user_id = "1234-5678-99ab-cdef"
test_user_username = "Test User1"
test_user_given_name = test_user_username.split(" ")[0]
test_user_surname = test_user_username.split(" ")[1]

class TestNewFlag(TestCase):
    @mock.patch('access.AccessClient.get_user_details', return_value={"user_id":test_user_id, "username":test_user_username})
    @mock.patch('api.run_sparql_update')
    def test_flag_to_visit(self, mock, mocker):
        flag_type = "http://nationaldigitaltwin.gov.uk/data#InterestedInVisiting"
        property_uri =  "http://telicent.io/test-data#123456"
        client = TestClient(api.app)
        response = client.post("/flag-to-visit", json={"uri": property_uri})
        arg = mock.call_args_list
        self.assertEqual(1, mock.call_count)
    
        graph = Graph()
        graph.update(arg[0][1]["query"])
        results = graph.query(f'''
        {format_prefixes()}
        SELECT  ?surname ?given_name ?flag_type ?flag ?property WHERE {{
            ?surname_ref a ies:Surname .
            ?surname_ref ies:representationValue ?surname . 
            ?given_name_ref a ies:GivenName . 
            ?given_name_ref ies:representationValue ?given_name . 
            ?person a ies:Person . 
            ?flag ies:isStateOf ?person .
            ?flag a ?flag_type . 
            ?flag ies:interestedIn ?property .
        }} ''').serialize(format="json")
        processed_results = flatten_out(loads( results), return_first_obj=True)
        self.assertEqual(processed_results['flag_type'], flag_type)
        self.assertEqual(processed_results['property'], property_uri)
        self.assertEqual(processed_results['given_name'], test_user_given_name)
        self.assertEqual(processed_results['surname'], test_user_surname)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), processed_results['flag'])
    
    @mock.patch('access.AccessClient.get_user_details', return_value={"user_id":test_user_id, "username":test_user_username})
    @mock.patch('api.run_sparql_update')
    def test_flag_to_investigate(self, mock, mocker):
        flag_type = "http://nationaldigitaltwin.gov.uk/data#InterestedInInvestigating"
        property_uri =  "http://telicent.io/test-data#123456"
        client = TestClient(api.app)
        response = client.post("/flag-to-investigate", json={"uri": property_uri}, headers={"x-amzn-oidc-data": "test-token-123"})
        arg = mock.call_args_list
        self.assertEqual(1, mock.call_count)
        self.assertEqual(arg[0][1]['forwarding_headers'], {"x-amzn-oidc-data": "test-token-123"})
        graph = Graph()
        graph.update(arg[0][1]["query"])

        results = graph.query(f'''
        {format_prefixes()}
        SELECT  ?surname ?given_name ?flag_type ?flag ?property WHERE {{
            ?surname_ref a ies:Surname .
            ?surname_ref ies:representationValue ?surname . 
            ?given_name_ref a ies:GivenName . 
            ?given_name_ref ies:representationValue ?given_name . 
            ?person a ies:Person . 
            ?flag ies:isStateOf ?person .
            ?flag a ?flag_type . 
            ?flag ies:interestedIn ?property .
        }} ''').serialize(format="json")
        processed_results = flatten_out(loads( results), return_first_obj=True)
        self.assertEqual(processed_results['flag_type'], flag_type)
        self.assertEqual(processed_results['property'], property_uri)
        self.assertEqual(processed_results['given_name'], test_user_given_name)
        self.assertEqual(processed_results['surname'], test_user_surname)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), processed_results['flag'])
        

def flatten_out(data, return_first_obj=False):
    results = []
    if data["results"]["bindings"] is not None:
        for stmt in data["results"]["bindings"]:
            obj = {}
            for v in data["head"]["vars"]:
                if v in stmt and stmt[v] is not None:
                    obj[v] = stmt[v]["value"]
            results.append(obj)
    if return_first_obj:
        return results[0]
    else:
        return results

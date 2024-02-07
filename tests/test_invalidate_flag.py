
from unittest import TestCase, mock
import os
os.environ['UPDATE_MODE'] = "FILE"
import api
from api import format_prefixes
from fastapi.testclient import TestClient
from rdflib import Graph
from json import loads

sub_types = ({'http://nationaldigitaltwin.gov.uk/ontology#AssessToBeFalse': {'uri': 'http://nationaldigitaltwin.gov.uk/ontology#AssessToBeFalse', 'shortName': 'ndt_ont:AssessToBeFalse', 'superClasses': ['http://ies.data.gov.uk/ontology/ies4#Assess'], 'description': []}, 'http://nationaldigitaltwin.gov.uk/ontology#AssessOccupantOptOutOrRefusal': {'uri': 'http://nationaldigitaltwin.gov.uk/ontology#AssessOccupantOptOutOrRefusal', 'shortName': 'ndt_ont:AssessOccupantOptOutOrRefusal', 'superClasses': ['http://nationaldigitaltwin.gov.uk/ontology#AssessToBeFalse', 'http://ies.data.gov.uk/ontology/ies4#AssessToBeFalse'], 'description': []}}, [{'uri': 'http://nationaldigitaltwin.gov.uk/ontology#AssessToBeFalse', 'shortName': 'ndt_ont:AssessToBeFalse', 'superClasses': ['http://ies.data.gov.uk/ontology/ies4#Assess'], 'description': []}, {'uri': 'http://nationaldigitaltwin.gov.uk/ontology#AssessOccupantOptOutOrRefusal', 'shortName': 'ndt_ont:AssessOccupantOptOutOrRefusal', 'superClasses': ['http://nationaldigitaltwin.gov.uk/ontology#AssessToBeFalse', 'http://ies.data.gov.uk/ontology/ies4#AssessToBeFalse'], 'description': []}])
test_user_id = "1234-5678-99ab-cdef"
test_user_username = "Test User1"
test_user_given_name = test_user_username.split(" ")[0]
test_user_surname = test_user_username.split(" ")[1]
class TestInvalidateFlags(TestCase):
    @mock.patch('api.get_subtypes', return_value=sub_types)
    @mock.patch('access.AccessClient.get_user_details', return_value={"user_id":test_user_id, "username":test_user_username})
    @mock.patch('api.run_sparql_update')
    def test_invalidate_flag(self, mock, mocker, update_mock):
        flag_uri = "http://telicent.io/test-data#123456"
        invalidation_reason =  "ndt_ont:AssessOccupantOptOutOrRefusal"
        full_invalidation_reason = "http://nationaldigitaltwin.gov.uk/ontology#AssessOccupantOptOutOrRefusal"
        client = TestClient(api.app)
        response = client.post("/invalidate-flag", json={"flagUri": flag_uri, "assessmentTypeOverride": invalidation_reason})
        arg = mock.call_args_list
        self.assertEqual(1, mock.call_count)
    
        graph = Graph()
        graph.update(arg[0][1]["query"])
        results = graph.query(f'''
        {format_prefixes()}
        SELECT  ?surname ?given_name ?flag ?invalidation_flag ?assessment WHERE {{
            ?surname_ref a ies:Surname .
            ?surname_ref ies:representationValue ?surname . 
            ?given_name_ref a ies:GivenName . 
            ?given_name_ref ies:representationValue ?given_name . 
            ?person a ies:Person . 
            ?assessment ies:assessor ?person .
            ?assessment a ?invalidation_flag . 
            ?assessment ies:assessed ?flag .
        }} ''').serialize(format="json")
        processed_results = flatten_out(loads( results), return_first_obj=True)
        self.assertEqual(processed_results['invalidation_flag'], full_invalidation_reason)
        self.assertEqual(processed_results['flag'], flag_uri)
        self.assertEqual(processed_results['given_name'], test_user_given_name)
        self.assertEqual(processed_results['surname'], test_user_surname)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), processed_results['assessment'])
        

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



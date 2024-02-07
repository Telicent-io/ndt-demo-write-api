import unittest
import os
os.environ['UPDATE_MODE'] = "FILE"
from api import create_person_insert, data_uri_stub, format_prefixes
from access import AccessClient
from rdflib import Graph
from rdflib.compare import to_isomorphic

class TestUserIes(unittest.TestCase):
    def test_shape_of_user(self):
        test_user_id = "1234-5678-99ab-cdef"
        test_user_username = "Test User1"
        test_user_given_name = test_user_username.split(" ")[0]
        test_user_surname = test_user_username.split(" ")[1]
        access_api = AccessClient(None, True)
        user = access_api.get_user_details([])
        
        self.assertEqual(user['user_id'], test_user_id)
        self.assertEqual(user['username'], test_user_username)

        uri, ies = create_person_insert(user['user_id'], user['username'])
        expected_uri = data_uri_stub + test_user_id

        self.assertEqual(uri, expected_uri)

        expected_ies = f'''
            {format_prefixes()}
            <{expected_uri}> a ies:Person .
            <{expected_uri}> ies:hasName <{expected_uri+"_NAME"}> .
            <{expected_uri+"_NAME"}> a ies:PersonName .
            <{expected_uri+"_SURNAME"}> a ies:Surname .
            <{expected_uri+"_SURNAME"}> ies:inRepresentation <{expected_uri+"_NAME"}> .
            <{expected_uri+"_SURNAME"}> ies:representationValue "{test_user_surname}" .
            <{expected_uri+"_GIVENNAME"}> a ies:GivenName .
            <{expected_uri+"_GIVENNAME"}> ies:inRepresentation <{expected_uri+"_NAME"}> .
            <{expected_uri+"_GIVENNAME"}> ies:representationValue "{test_user_given_name}" .
        '''
 

        expected_graph = to_isomorphic(Graph().parse( data=expected_ies))
        ies_graph = to_isomorphic(Graph().parse(data=f"{format_prefixes()}\n"+ies))
        self.assertEqual(expected_graph, ies_graph)




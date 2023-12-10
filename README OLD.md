# ndt-demo-write-api
A simple API for controlled addition of data in environments where free text is not appropriate

The NDT Assessment Write-Back API was developed to provide NDT users a strictly controlled way to create new data in a Telicent CORE deployment.

The data creation is centred around states of buildings and the IES AssessToBeTrue event.

## Running the server

If you want to run this locally, you'll need to:

* install Apache Jena Fuseki - https://jena.apache.org/download/index.cgi
* run Apache Jena Fuseki
* create two datasets in Fuseki - ontology and knowledge
* load the ontology ttl files in this repo into the ontology dataset (again, use the Fuseki UI) - this will provide the API with access to the ontologies
* add your test data (e.g. buildings.ttl) to the knowledge dataset
* pip install all the modules listed in requirements.txt
* run the api.py file or the run-api.sh script (Python 3.9 or later) 

## Using the API

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

The API will (eventually) detect the user logged in and use the user ID to create a person. For testing purposes, in the short term, this will just be a single test user (synthetic data)


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

An Insomnia (https://insomnia.rest/) test suite is also provided as a JSON config file - `ndt-write-insomnia.json`

## Security

Telicent CORE uses a label-based approach to access control, based on the UK Govt Enterprise Data Headers standard - policy based access control, in other words. In all the IES post operations, you can set a securityLabel property that will override the default label.

You can also get and set the default security label. 
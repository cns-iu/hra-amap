import random
import uuid

rd = random.Random()
rd.seed(12)

donor = {
    'sex': 'Female', 
    'label': 'label',
    'provider_name': 'MC-IU', 
    'provider_uuid': str(uuid.UUID(int=rd.getrandbits(128), version=4)), 
    'consortium_name': 'HRA',
    'id': 'https://purl.humanatlas.io/millitome/generic-ovary-female-right',      # make necessary edits here
    'link': 'https://purl.humanatlas.io/millitome/generic-ovary-female-right'        # make necessary edits here
}
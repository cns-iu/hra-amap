rui_location = {
    '@context': "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld",
    # '@id': f"{donor['id']}#{label}",
    '@type': 'SpatialEntity',
    'creator': 'Antara Bhavsar',      # make necessary edits here
    'creator_first_name': 'Antara',     # make necessary edits here
    'creator_last_name': 'Bhavsar',       # make necessary edits here
    'creator_orcid': 'https://orcid.org/0009-0008-6509-7698',       # make necessary edits here
    # 'label': label,
    # 'creation_date': datetime.today().strftime('%Y-%m-%d'), 
    'dimension_units': 'millimeter', 
    'placement': {'@context': "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld",
                # '@id': f"{donor['id']}#{label}_placement", 
                '@type': 'SpatialPlacement', 
                # 'target': f'http://purl.org/ccf/latest/ccf.owl#{target_name}', 
                # 'placement_date': datetime.today().strftime('%Y-%m-%d'), 
                'scaling_units': 'ratio', 
                'rotation_order': 'XYZ', 
                'rotation_units': 'degree', 
                'translation_units': 'millimeter'
                }
}
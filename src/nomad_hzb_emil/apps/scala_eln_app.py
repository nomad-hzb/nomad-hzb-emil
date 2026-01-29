from nomad.config.models.ui import (
    App,
    Column,
    Columns,
    FilterMenu,
    FilterMenus,
    Filters,
)

# nomad-oasis/gui/search/sscala-eln?optimade_filter=upload_name%20CONTAINS%20"D8"
scala_eln_app = App(
    label='SCALA',
    path='scala-eln',
    category='EMIL',
    description="""
    Explore the data from the SCALA lab.
    """,
    readme="""
    Explore the data from the SCALA lab.
    """,
    filters=Filters(
        include=[
            # '*#nomad_chemical_energy.schema_packages.hzb_catlab_package.CatLab_XYSample',
        ]
    ),
    columns=Columns(
        selected=[
            'results.material.elements',
            'entry_type',
            'results.eln.methods',
            'entry_type',
            'authors',
            'upload_name'


        ],
        options={
            'entry_type': Column(label='Entry type', align='left'),
            'entry_name': Column(label='Name', align='left'),
            'entry_create_time': Column(label='Entry time', align='left'),
            'authors': Column(label='Authors', align='left'),
            'upload_name': Column(label='Upload name', align='left'),
            'results.material.elements': Column(label='Elements', align='left'),
        },
    ),
    filters_locked={
        'authors.name': 'Scala Hzb'  # display only uploads from Scala lab
        # 'authors.name': 'Dimitra Gkogkou'  # for local test
        # 'section_defs.definition_qualified_name': 'nomad_chemical_energy.schema_packages.hzb_catlab_package.CatLab_XYSample'
    },
    filter_menus=FilterMenus(
        options={
            'material': FilterMenu(label='Material', level=0),
            'elements': FilterMenu(label='Elements / Formula', level=1, size='xl'),
            'eln': FilterMenu(label='Electronic Lab Notebook', level=0),
            'custom_quantities': FilterMenu(
                label='User Defined Quantities', level=0, size='l'
            ),
            'author': FilterMenu(label='Author / Origin / Dataset', level=0, size='m'),
            'metadata': FilterMenu(label='Visibility / IDs / Schema', level=0),
            'optimade': FilterMenu(label='Optimade', level=0, size='m'),
        }
    ),
    dashboard={
        'widgets': [


            # Upload selector
            {
                'type': 'terms',
                'show_input': True,
                'search_quantity': 'upload_name',
                'title': 'Select Upload',
                'layout': {
                    'xxl': {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 6},
                    'xl':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 0},
                    'lg':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 5, 'y': 0, 'x': 5},
                    'md':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 6},
                    'sm':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 6},
                },
            },

            # Methods/schema selection
            {
                'type': 'terms',
                'show_input': True,
                'search_quantity': 'results.eln.sections',
                'title': 'Select Type',
                'layout': {
                    'xxl': {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 12},
                    'xl':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 20},
                    'lg':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 5, 'y': 0, 'x': 10},
                    'md':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 12},
                    'sm':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 6, 'y': 0, 'x': 12},
                },
            },


            # Element selector (periodic table)
            {
                'type': 'periodic_table',
                'search_quantity': 'results.material.elements',
                'title': 'Select Material(s)',
                'layout': {
                    'xxl': {'minH': 3, 'minW': 3, 'h': 9, 'w': 12, 'y': 0, 'x': 12},
                    'xl':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 10, 'y': 0, 'x': 10},
                    'lg':  {'minH': 3, 'minW': 3, 'h': 6, 'w': 9,  'y': 0, 'x': 15},
                    'md':  {'minH': 3, 'minW': 3, 'h': 9, 'w': 12, 'y': 0, 'x': 12},
                    'sm':  {'minH': 3, 'minW': 3, 'h': 9, 'w': 12, 'y': 0, 'x': 12},
                },
            },


        ]
    },
)

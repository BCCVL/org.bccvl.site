from setuptools import setup, find_packages
import os

version = '0.9.0-rc1'

setup(
    name='org.bccvl.site',
    version=version,
    description="BCCVL Policy Product",
    # long_description=open("README.txt").read() + "\n" +
    #                  open(os.path.join("docs", "HISTORY.txt")).read(),
    # Get more strings from
    # http://pypi.python.org/pypi?:action=list_classifiers
    classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
    ],
    keywords='',
    author='',
    author_email='',
    url='http://svn.plone.org/svn/collective/',
    license='GPL',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['org', 'org.bccvl'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',  # distribute
        'org.bccvl.theme',
        'Products.AutoUserMakerPASPlugin',
        'Products.ShibbolethPermissions',
        'sc.social.like',
        'gu.repository.content',
        'gu.transmogrifier',
        'collective.js.jqueryui',
        'collective.js.uix.multiselect',
        'collective.geo.contentlocations',
        'collective.geo.geographer',
        'collective.geo.kml',
        'collective.geo.mapwidget',
        'collective.geo.openlayers',
        'collective.geo.settings',
        'collective.z3cform.mapwidget',
        'collective.googleanalytics',
        'collective.quickupload',
        'collective.onlogin',
        'collective.z3cform.widgets',
        'collective.z3cform.wizard',
        #'collective.z3cform.chosen',
        'gu.plone.rdf',
        'plone.app.folderui',
        'dexterity.membrane',
        'borg.localrole',
        'plone.app.contenttypes',
        'decorator',
        'collective.setuphelpers',
        'plone.app.contentlisting',
        'collective.transmogrifier',
        'collective.blueprint.jsonmigrator',
        'transmogrify.dexterity',
        'quintagroup.transmogrifier',
        'org.bccvl.compute',
        #'python-openid', # enable openid
        #'plone.app.openid',  # try to load configure stuff
        #'atreal.richfile.qualifier',
        #'atreal.richfile.image',
        #'atreal.richfile.preview',
        #'atreal.richfile.streaming',
        #'atreal.richfile.metadata',
        #'atreal.filestorage.common',
        #'atreal.filestorage.blobfile',
        #'atreal.filecart',
        #'atreal.layouts', # MatrixView
        # 'affinitic.zamqp',
        # 'pika == 0.5.2', -> rather us kombu
        # TODO: verify that we need this.
        #'plone.app.relationfield',
    ],
    extras_require={
        'test': ['plone.app.testing',
                 'unittest2']
    },

    entry_points="""
    # -*- Entry points: -*-
    [z3c.autoinclude.plugin]
    target = plone
    """,
    )

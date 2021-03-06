from setuptools import setup, find_packages

setup(
    name='org.bccvl.site',
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
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
        'Plone',
        'five.pt',
        'org.bccvl.theme',
        'org.bccvl.movelib[swift]',
        'Products.AutoUserMakerPASPlugin',
        'Products.ShibbolethPermissions',
        'Products.CMFPlacefulWorkflow',
        'plone.app.dexterity',
        'gu.transmogrifier',
        'plone.api',
        'collective.js.jqueryui',
        'collective.googleanalytics',
        'collective.onlogin',
        'collective.indexing',
        'collective.emailconfirmationregistration',
        'plone.formwidget.captcha',
        'plone.formwidget.recaptcha',
        'collective.z3cform.norobots',
        #'collective.deletepermission', careful it interfers with delete buttons when not activated
        'borg.localrole',
        'plone.app.contenttypes',
        'decorator',
        'plone.app.contentlisting',
        'collective.transmogrifier',
        'collective.jsonmigrator',
        'transmogrify.dexterity',
        'org.bccvl.compute',
        'org.bccvl.tasks',
        'org.bccvl.movelib[http,swift]',
        'requests-oauthlib',
        'rdflib',
        'eea.facetednavigation',
        'plone.restapi',
        # TODO: deprecated, but needed here due to zcml autoinclude
        'Products.AdvancedQuery',  # optional anyway but hard import atm
    ],
    extras_require={
        'test': [
            'plone.app.testing',
            'mock',
            'org.bccvl.tasks[metadata]',
        ],
        'deprecated':  [
        ],
        'experimental': [
        ],
        'wsgi': [
            'Paste',
            'PasteScript',
            'repoze.tm2',
            'repoze.retry'
        ]
    },

    entry_points="""
    # -*- Entry points: -*-
    [z3c.autoinclude.plugin]
    target = plone
    """,
)

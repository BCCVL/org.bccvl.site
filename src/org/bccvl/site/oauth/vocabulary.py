from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


@implementer(IVocabularyFactory)
class OAuthProviderVocabularyFactory(object):

    # we store registered providers on the class
    providers = []

    def __init__(self):
        self.vocab = None

    # TODO: this should rather be module global
    def add_provider(self, interface, title):
        self.providers.append((interface, title))
        self.vocab = None

    def __call__(self, context):
        if self.vocab is None:
            self.vocab = SimpleVocabulary([
                SimpleTerm(pr[0],
                           pr[0].__identifier__,
                           pr[1]) for pr in self.providers])
        return self.vocab


oauth_providers = OAuthProviderVocabularyFactory()

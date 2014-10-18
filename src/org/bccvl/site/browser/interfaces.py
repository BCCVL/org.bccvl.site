from zope.interface import Interface


class IDatasetTools(Interface):

    def get_transition(itemob=None):
        """
        return list of possible workflow transitions on current context or
        itemob?
        """

    def get_download_info(item=None):
        """
        get download info dict for current context or item.
        """

    def can_modify(itemob=None):
        """
        return true if current user has permission cmf.ModifyPortalContent
        on context or itemob
        """

    def local_roles_action(itemobj=None):
        """
        return action info dictionary for local_roles action.
        ("Sharing Options")
        """

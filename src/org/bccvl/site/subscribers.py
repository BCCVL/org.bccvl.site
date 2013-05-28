from Products.CMFCore.utils  import getToolByName

def InitaliseUser(user, event):
    # FIXME: do nothing here for now ....
    #         clashes with manually created users.
    # FIXME: auto user maker places stuff into mutable_properties ...
    #        we need them here on the content object itself....
    
    # on first login we fix up auto user creation.
    # AutoUserMaker put's information like fullname and email into 'mutable_properties'
    # we want them also in mebrane_properties and on the object itself
    #
    # object is a Products.membrane.plugins.userfactory.MembraneUser
    # event is a Products.PlonePAS.events.UserInitialLoginInEvent
    
    #poperty sheets are on user, 
    mutprops = user.getPropertysheet('mutable_properties')

    newprops  = {}
    for prop in ('fullname', 'email'):
        val = mutprops.getProperty(prop)
        if val:
            newprops[prop] = val
    memprops = user.getPropertysheet('membrane_properties')
    memprops.setProperties(user, newprops)

    membrane_tool = getToolByName(user, 'membrane_tool')
    userobj = membrane_tool.getUserObject(user.getUserId())
    # TODO: this here works only with current FacultyStaffDirectory person objects
    nameparts = user.getProperty('fullname').split()
    # other fields are on userobj
    if len(nameparts) == 1:
        userobj.first_name = ''
        userobj.last_name = nameparts[0]
    elif len(nameparts) > 1:
        userobj.first_name = nameparts[0]
        userobj.last_name = nameparts[-1]
    else:
        # should do something interesting here
        # e.g. use userid, or extract email, etc...
        pass

    
    # don't forget to reindex     
    userobj.reindexObject()    
    


# there is also: UserLoggedInEvent for existing users... good point to update info?
#    ... e.g. if data is not consistent then redirect to homepage :)

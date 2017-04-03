import adsk.core, adsk.fusion, adsk.cam, traceback

from xml.etree import ElementTree
from xml.etree.ElementTree import SubElement

from os.path import expanduser
import os
import tempfile
import subprocess

# Global Variable to handle command events
_app = adsk.core.Application.get()
_ui  = _app.userInterface
handlers = []

# Global Program ID for settings
programID = 'Fab_Fusion'
                
def getFileName():
    
    # Get user's home directory
    home = expanduser("~")
    
    # Create a subdirectory for this application settings
    home += '/' + programID + '/'
    
    # Create the folder if it does not exist
    if not os.path.exists(home):
        os.makedirs(home)
    
    # Get full path for the settings file
    xmlFileName = home  + 'settings.xml'
    
    return xmlFileName

# Write users settings to a local file 
def writeSettings(xmlFileName, host, Fab_post, showOperations):
    
    # If the file does not exist create it
    if not os.path.isfile(xmlFileName):
        # Create the file
        new_file = open( xmlFileName, 'w' )                        
        new_file.write( '<?xml version="1.0"?>' )
        new_file.write( '<' + programID + ' /> ')
        new_file.close()
        
        # Open the file and parse as XML        
        tree = ElementTree.parse(xmlFileName) 
        root = tree.getroot()
    
    # Read in the file and get the tree
    else:
        tree = ElementTree.parse(xmlFileName) 
        root = tree.getroot()
        
        # Remove old settings info
        root.remove(root.find('settings'))
    
    # Write settings info into XML file
    settings = SubElement(root, 'settings')
    SubElement(settings, 'host', value = host) # this will be the FabMo Address
    SubElement(settings, 'Fab_post', value = Fab_post)
    SubElement(settings, 'showOperations', value = showOperations)

    # Write settings to XML File
    tree.write(xmlFileName)

# Post process selected operation and send to FabMo
def exportFile(opName, Fab_post, isDebug):

    app = adsk.core.Application.get()
    doc = app.activeDocument
    products = doc.products
    product = products.itemByProductType('CAMProductType')
    cam = adsk.cam.CAM.cast(product)

     #Iterate through CAM objects for operation, folder or setup
     #Currently doesn't handle duplicate in names
    for setup in cam.setups:
        if setup.name == opName:
            toPost = setup
        else:
            for folder in setup.folders:
                if folder.name == opName:
                    toPost = folder
   
    for operation in cam.allOperations:
        if operation.name == opName:
            toPost = operation
            
    # Create a temporary directory for post file
    #outputFolder = tempfile.mkdtemp()
    outputFolder = cam.temporaryFolder
   
    # Set the post options        
    postConfig = os.path.join(cam.genericPostFolder, Fab_post) 
    units = adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput

    # create the postInput object
    postInput = adsk.cam.PostProcessInput.create(opName, postConfig, outputFolder, units)
    postInput.isOpenInEditor = False
    cam.postProcess(toPost, postInput)
    
    import time
    time.sleep(3)
    # Get the resulting filename
    resultFilename = os.path.join(outputFolder , opName + '.nc')
              
    # Get list of tools on the network
    from .Modules import fabmo    
    try:
        tools = fabmo.find_tools(debug=isDebug)
    except Exception as e:
        _ui.messageBox(e)
        return False
        
    # Make sure we have one and only one tool
    if len(tools) == 0:
        _ui.messageBox('No tools were found on the network.')
        return
    elif len(tools) > 1:
        _ui.messageBox('There is more than one tool on the network.')
        return
        
    tool = tools[0]

    with open(resultFilename) as fp:
        gcode = fp.read()
        gcode = gcode.replace('%','')
        job = tool.submit_job(gcode, opName + '.nc', opName + ' From Fusion 360.') # right now we are only supporting operations
            
    _ui.messageBox('Job submitted.')
    tool.show_job_manager()
            
    return True
    
    #except:
        #if _ui:
            #_ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Get the current values of the command inputs.
def getInputs(inputs):

        from .Modules import fabmo    
        tools = fabmo.find_tools(False)

        # Look up name of input and get value
        Fab_post = inputs.itemById('Fab_post').text
        saveSettings = inputs.itemById('saveSettings').value
        showOperationsInput = inputs.itemById('showOperations')
        showOperations = showOperationsInput.selectedItem.name

        # Only attempt to get a value if the user has made a selection
        setupInput = inputs.itemById('setups')
        setupItem = setupInput.selectedItem
        if setupItem:
            setupName = setupItem.name
        
        folderInput = inputs.itemById('folders')
        folderItem = folderInput.selectedItem
        if folderItem:
            folderName = folderItem.name
        
        operationInput = inputs.itemById('operations')
        operationItem = operationInput.selectedItem
        if operationItem:
            operationName = operationItem.name
        
        # Get the name of setup, folder, or operation depending on radio selection
        # This is the operation that will post processed and here is where we define the name of our operation
        if (showOperations == 'Setups'):
            opName = setupName
        elif (showOperations == 'Folders'):
            opName = folderName
        elif (showOperations == 'Operations'):
            opName = operationName

        return (opName, Fab_post, saveSettings, showOperations, tools)

# Will update visibility of 3 selection dropdowns based on radio selection
# Also updates radio selection which is only really useful when command is first launched.
def setDropdown(inputs, showOperations):
    
    # Get input objects
    setupInput = inputs.itemById('setups')
    folderInput = inputs.itemById('folders')
    operationInput = inputs.itemById('operations')
    showOperationsInput = inputs.itemById('showOperations')

    # Set visibility based on appropriate selection from radio list
    if (showOperations == 'Setups'):
        setupInput.isVisible = True
        folderInput.isVisible = False
        operationInput.isVisible = False
        showOperationsInput.listItems[0].isSelected = True
    elif (showOperations == 'Folders'):
        setupInput.isVisible = False
        folderInput.isVisible = True
        operationInput.isVisible = False
        showOperationsInput.listItems[1].isSelected = True
    elif (showOperations == 'Operations'):
        setupInput.isVisible = False
        folderInput.isVisible = False 
        operationInput.isVisible = True
        showOperationsInput.listItems[2].isSelected = True
    else:
        # TODO add error check
        return
    return

# Define the event handler for when the command is executed THIS IS THE START OF THE End
class FabExecutedEventHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get the inputs.
            inputs = args.command.commandInputs
            (opName, Fab_post, saveSettings, showOperations, tools) = getInputs(inputs)
            
            # Save Settings:
            if saveSettings:
                xmlFileName = getFileName()
                writeSettings(xmlFileName, host, Fab_post, showOperations)
            
# def writeSettings(xmlFileName, host, Fab_post, showOperations):

            # Export the file and contact FabMo
            exportFile(opName, Fab_post, inputs.itemById('debugInput').value)
            
        except:
            app = adsk.core.Application.get()
            ui  = app.userInterface
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Define the event handler for when any input changes.
class FabInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get inputs and changed inputs
            input_changed = args.input
            inputs = args.inputs

            # Check to see if the post type has changed and show appropriate drop down
            if input_changed.id == 'showOperations':
                showOperations = input_changed.selectedItem.name
                setDropdown(inputs, showOperations)
                
        except:
            app = adsk.core.Application.get()
            ui  = app.userInterface
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
               
# Define the event handler for when the Fab_Fusion command is run by the user.
class FabCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        ui = []
        try:
            app = adsk.core.Application.get()
            ui  = app.userInterface
            doc = app.activeDocument
            products = doc.products
            product = products.itemByProductType('CAMProductType')

            # Check if the document has a CAMProductType. It will not if there are no CAM operations in it.
            if product == None:
                 ui.messageBox('There are no CAM operations in the active document')
                 return            
            # Cast the CAM product to a CAM object (a subtype of product).
            cam = adsk.cam.CAM.cast(product)

            # Connect to the command executed event.
            cmd = args.command
            cmd.isExecutedWhenPreEmpted = False
            
            onExecute = FabExecutedEventHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)

            onInputChanged = FabInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            handlers.append(onInputChanged)

            # Define the inputs.
            inputs = cmd.commandInputs
            
            # Labels
            inputs.addTextBoxCommandInput('labelText3', '', 'Post Process and send CAM Setups, Folders, or Operations directly to a tool running FabMo on the network', 2, True)
            
            inputs.addImageCommandInput('', '', './/resources//FabMo_G2_logo.png')

            # FabMo local path and post information 
            Fab_post_input = inputs.addTextBoxCommandInput('Fab_post', 'Name of Post', 'shopbot iso.cps', 1, False)
            
            # What to select from?  Setups, Folders, Operations?
            showOperations_input = inputs.addButtonRowCommandInput("showOperations", 'What to Post?', False)  
            showOperations_input.listItems.add("Setups", False, './/Setups')
            showOperations_input.listItems.add("Operations", True, './/Operations')
            showOperations_input.listItems.add("Folders", False, './/Folders')

            # Drop down for Setups
            setupDropDown = inputs.addDropDownCommandInput('setups', 'Select Setup:', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            # Drop down for Folders
            folderDropDown = inputs.addDropDownCommandInput('folders', 'Select Folder:', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            # Drop down for Operations
            opDropDown = inputs.addDropDownCommandInput('operations', 'Select Operation:', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
        
            # Populate values in dropdowns based on current document:
            for setup in cam.setups:
                setupDropDown.listItems.add(setup.name, False)
                for folder in setup.folders:
                    folderDropDown.listItems.add(folder.name, False)         
            for operation in cam.allOperations:
                opDropDown.listItems.add(operation.name, False)

            # Drop down for available tools
            toolDropDown = inputs.addDropDownCommandInput('tools', 'Select Tool:', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            # toolDropDown.listItems.add(tool.name, False)

            # Option for debuging mode from StoolDesign    
            debugInput = inputs.addBoolValueInput('debugInput', 'Debug Mode', True, '', False)

            # Save user settings, values written to local computer XML file
            inputs.addBoolValueInput("saveSettings", 'Save settings?', True)
            
            # Defaults for command dialog
            cmd.commandCategoryName = 'FabMo'
            cmd.setDialogInitialSize(500, 300)
            cmd.setDialogMinimumSize(500, 300)
            cmd.okButtonText = 'POST'  
            
            # Check if user has saved settings and update UI to reflect preferences
            xmlFileName = getFileName()
            if os.path.isfile(xmlFileName):
                
                # Read Settings                
                (Fab_post, showOperations) = readSettings(xmlFileName)
                
                # Update dialog values
                Fab_post_input.text = Fab_post
                setDropdown(inputs, showOperations)
            else:
                setDropdown(inputs, 'Operations') #This is where we set the default value and could be source of bug?

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def run(context):
    ui = None

    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface

        if ui.commandDefinitions.itemById('FabButtonID'):
            ui.commandDefinitions.itemById('FabButtonID').deleteMe()

        # Get the CommandDefinitions collection.
        cmdDefs = ui.commandDefinitions

        # Create a button command definition for the comamnd button. 
        tooltip = '<div style=\'font-family:"Calibri";\'><span style=\'font-size:12px;\'><b>Post Process and send CAM Setups, Folders, or Operations directly to a tool running FabMo on the network'
        FabButtonDef = cmdDefs.addButtonDefinition('FabButtonID', 'Post to FabMo', tooltip, './/resources')
        onFabCreated = FabCreatedEventHandler()
        FabButtonDef.commandCreated.add(onFabCreated)
        handlers.append(onFabCreated)

        # Find the "ADD-INS" panel for the solid and the surface workspaces.
        solidPanel = ui.allToolbarPanels.itemById('CAMActionPanel')
        
        # Add a button for the "Request Quotes" command into both panels.
        solidPanel.controls.addCommand(FabButtonDef, '', False)
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface

        if ui.commandDefinitions.itemById('FabButtonID'):
            ui.commandDefinitions.itemById('FabButtonID').deleteMe()

        # Find the controls in the solid and surface panels and delete them.
        camPanel = ui.allToolbarPanels.itemById('CAMActionPanel')
        cntrl = camPanel.controls.itemById('FabButtonID')
        if cntrl:
            cntrl.deleteMe()


    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

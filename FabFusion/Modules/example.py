import fabmo

GCODE = '''(Inches)
G20
(Pull Up)
G0 Z0.25
(Move Home)
G0 X0Y0
(Spindle On)
M4
(Plunge)
G1 Z-0.0625 F30
(Engrave Square)
G1 X1 F60
G1 Y1
G1 X0
G1 Y0
(Pull Up)
G0 Z0.25
(Spindle Off)
M8
(Go Home)
G0 X0Y0
'''

def main():
    # Get list of tools on the network
    # (if debug=True, then this will return a list with only one tool: The demo at http://demo.gofabmo.org/)
    tools = fabmo.find_tools(debug=True)

    # Make sure we have one and only one tool
    if len(tools) == 0:
        raise Exception('No tools were found on the network.')
    elif len(tools) > 1:
        raise Exception('There is more than one tool on the network.')

    tool = tools[0]
    print("Tool Status: " + str(tool.get_status()))
    job = tool.submit_job(GCODE, 'square.nc', '1-Inch Square' , 'Engrave a square, one inch on a side, to a depth of 1/16" at 1 inch/sec')
    print("Submitted Job: " + str(job))
    tool.show_job_manager()

if __name__ == "__main__":
    main()

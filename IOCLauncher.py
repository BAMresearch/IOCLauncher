from pathlib import Path
from dash import Dash, html, dcc, Input, Output, State, callback_context
import dash
import subprocess
from datetime import datetime
import os
import yaml
import flask
from flask import send_file
import dash_bootstrap_components as dbc
import psutil
import plotly.graph_objs as go
import numpy as np
import plotly.express as px

global HeartbeatCount
HeartbeatCount = 0  # Add a global variable to track the number of heartbeat checks

# for graphing of CPU and Network usage
cpu_load_history = []
network_sent_history = []
network_recv_history = []
timestamps = []

# Maximum points to store (30 minutes of data, updated every 2 seconds)
MAX_POINTS = 900

# Generate a list of colors for the CPU load values using Plotly's color scales
def get_color_for_values(values, scale=px.colors.sequential.Inferno, max_value:float=100):
    norm_values = [float(i)/max_value for i in values]  # Normalize values to 0-1
    colors = px.colors.sample_colorscale(scale, norm_values, colortype='rgb')#[0] for val in values
    # colors = [px.colors.sample_colorscale(scale, val)[0] for val in norm_values]
    colors_with_alpha = [colors[i].replace('rgb', 'rgba').replace(')', f', {norm_values[i]:0.03f})') for i in range(len(colors))]
    return colors_with_alpha

# Load IOC configurations from a YAML file
def load_ioc_config(file_path='iocs.yaml'):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)["IOCs"]

# Function to start an IOC process
def start_ioc(ioc):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = Path(log_dir, f"{ioc['name']}_{timestamp}.log")

    command = f"{ioc['command']} > {log_filename} 2>&1"

    process = subprocess.Popen(command, shell=True, universal_newlines=True)

    # # Start the process with Popen and redirect stdout and stderr
    # process = subprocess.Popen(ioc['command'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, bufsize=1, universal_newlines=True)
    
    # # Open the log file for writing
    # with open(log_filename, "w") as log_file:
    #     while True:
    #         output = process.stdout.readline()
    #         if output == '' and process.poll() is not None:
    #             break
    #         if output:
    #             log_file.write(output)
    #             log_file.flush()

    return process, log_filename

# Function to stop an IOC process
def stop_ioc(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
ioc_config = load_ioc_config()

# Track running processes and their log files
processes = {ioc['name']: {'process': None, 'log': None} for ioc in ioc_config}

app.layout = html.Div([
    html.H1("IOC Manager", style={'text-align': 'center'}, className="mb-4"),
    dcc.Interval(id='performance-update', interval=2000, n_intervals=0),
    html.Div(id="ioc-list"),
    dcc.Interval(id='update-interval', interval=2000, n_intervals=0),
    html.Div(id='log-output', className='log-modal'),
    html.Div([
    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=2000,  # 2000 milliseconds = 2 seconds
        n_intervals=0
    )
    ])
])


# Fancy, unnecessary graphing of CPU and Network usage
@app.callback(Output('live-update-graph', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
    # Capture the current time and system metrics
    now = datetime.now()
    cpu_percent = np.maximum(psutil.cpu_percent(), 0.001)  # Avoid division by zero
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent
    bytes_recv = net_io.bytes_recv

    # Append data, removing the oldest data point if at max capacity
    timestamps.append(now)
    cpu_load_history.append(cpu_percent)
    network_sent_history.append(bytes_sent)
    network_recv_history.append(bytes_recv)

    if len(cpu_load_history) > MAX_POINTS:
        timestamps.pop(0)
        cpu_load_history.pop(0)
        network_sent_history.pop(0)
        network_recv_history.pop(0)

    sent_deltas = [j-i for i, j in zip(network_sent_history[:-1], network_sent_history[1:])]
    recv_deltas = [j-i for i, j in zip(network_recv_history[:-1], network_recv_history[1:])]

    # Generate colors for CPU load values
    cpu_colors = get_color_for_values(cpu_load_history)

    fig = go.Figure()

    # CPU Load - Plot as bars on secondary Y-axis
    fig.add_trace(go.Bar(x=timestamps, y=cpu_load_history, name='CPU Load (%)', 
                     marker=dict(color=cpu_colors), yaxis='y2', width=1500))  # Example width

    # Network Load - Use primary Y-axis
    fig.add_trace(go.Scatter(x=timestamps[1:], y=sent_deltas, mode='lines', name='Network Sent (bytes)'))
    fig.add_trace(go.Scatter(x=timestamps[1:], y=recv_deltas, mode='lines', name='Network Received (bytes)'))

    # fig.add_trace(go.Bar(x=timestamps, y=cpu_load_history, name='CPU Load (%)', marker=dict(color=cpu_colors), yaxis='y2'))

    # Layout adjustments including secondary y-axis configuration
    fig.update_layout(
        # Layout configuration
        title='System Load Over the Last 30 Minutes',
        xaxis_title='Time',
        yaxis=dict(title='Network Load (bytes)', showgrid=False),
        yaxis2=dict(
            title='CPU Load (%)',
            overlaying='y',
            side='right',
            range=[0, 100],
            showgrid=True,
            gridcolor='lightgrey',
            # Secondary y-axis label and tick colors can be adjusted as needed
        ),
        legend_title='Metric',
        uirevision='constant',
        height=350,  # Adjust the graph height
    )
    fig.update_layout(
        legend=dict(x=0.002, y=0.98, xanchor='auto'),  # Adjust legend position
        margin=dict(r=150)  # Add right margin to the figure    
    )

    return fig


# Update the IOC list every 2 seconds
@app.callback(
    Output('ioc-list', 'children'),
    [Input('update-interval', 'n_intervals')]
)
def update_ioc_list(_):
    rows = []
    for ioc in ioc_config:
        status = "Stopped"
        button_text = "Start"
        button_action = 'start'
        button_color = 'primary'
        log_link = ""
        
        process_info = processes.get(ioc['name'])
        if process_info and process_info['process']:
            if process_info['process'].poll() is None:
                status = "Running"
                button_text = "Stop"
                button_color = 'warning'
                button_action = 'stop'
            else:
                status = "Crashed"

        if ioc['name'] == "Heartbeat":
            status = "Beating"
            button_text = "Check"
            button_action = 'stop'

            # log_link = f'/logs/{os.path.basename(process_info["log"])}' if process_info['log'] else '#'

        row = dbc.Row([
            dbc.Col(html.Div(ioc['name']), width=3, style={'text-align': 'right'}, className="custom-padding-left"),
            dbc.Col(html.Div(status), width=1),
            dbc.Col(dbc.Button(button_text, id={'type': button_action, 'index': ioc['name']}, color=button_color, className="custom-button-height"), width=1),
            dbc.Col(html.A(dbc.Button("View Log", color="primary", className="custom-button-height" ), href=f'/logs/{process_info["log"].name}', target="_blank") if process_info['log'] else '', width = 1), # if log_link != '#' else "", width=3),
        ], className="mb-3")
        rows.append(row)
    return rows


@app.callback(
    Output('log-output', 'children'),
    [Input({'type': 'start', 'index': dash.ALL}, 'n_clicks'),
     Input({'type': 'stop', 'index': dash.ALL}, 'n_clicks')],
    [State({'type': 'start', 'index': dash.ALL}, 'id'),
     State({'type': 'stop', 'index': dash.ALL}, 'id')]
)
def handle_start_stop(start_clicks, stop_clicks, start_ids, stop_ids):
    ctx = callback_context
    triggered = ctx.triggered[0]
    button_id = triggered['prop_id'].split('.')[0]
    action, ioc_name = eval(button_id)['type'], eval(button_id)['index']

    # Check if the IOC is the "Heartbeat" entry. The first entry for some reason is always started, so we turned it into a "Heartbeat" check
    if ioc_name == "Heartbeat":
        # Optionally update UI or perform a lightweight check operation here
        global HeartbeatCount
        HeartbeatCount += 1
        return f"Heartbeat check performed. {HeartbeatCount=} "  

    if action == 'start':
        for ioc in ioc_config:
            if ioc['name'] == ioc_name and (not processes[ioc_name]['process'] or processes[ioc_name]['process'].poll() is not None):
                process, log_filename = start_ioc(ioc)
                processes[ioc_name] = {'process': process, 'log': log_filename}
                return f"Started {ioc_name}, log at {log_filename}"
    elif action == 'stop':
        if processes[ioc_name]['process'] and processes[ioc_name]['process'].poll() is None:
            stop_ioc(processes[ioc_name]['process'])
            processes[ioc_name]['process'] = None
            return f"Stopped {ioc_name}"
    return dash.no_update

# Assuming your Dash app is named 'app'
server = app.server

@server.route('/logs/<log_filename>')
def serve_log_file(log_filename: str) -> flask.Response:
    log_dir = "logs"  # The directory where your log files are stored
    file_path = Path(log_dir, log_filename)
    # file_path = os.path.join(log_dir, log_filename)
    # print(f'opening log file {file_path=}')
    if file_path.exists():
        return send_file(file_path)
    return flask.abort(404, description=f"Log file not found at {file_path}")

if __name__ == '__main__':
    app.run_server(debug=True)

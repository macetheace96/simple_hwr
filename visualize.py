import pickle, json
from pathlib import Path
import os
from visdom import Visdom
import numpy as np
import torch
import warnings
import json
from crnn import Stat

## Some functions stolen from https://github.com/theevann/visdom-save

class Plot(object):
    def __init__(self, title="", env_name="", config=None, port=8080):
        self.env_name = env_name if env_name else title
        self.viz = Visdom(port=port, env=self.env_name)
        #self.viz.close()
        self.windows = {}
        self.title = title
        self.config = config


    def register_plot(self, name, xlabel, ylabel, plot_type="line", ymax=None):
        self.windows[name] = {"xlabel":xlabel, "ylabel":ylabel, "title":name, "plot_type":plot_type}
        self.windows[name]["opts"] = dict(title=name, markersize=5, xlabel=xlabel, ylabel=ylabel)

        if ymax is not None:
            self.windows[name]["opts"]["layoutopts"] = dict(plotly=dict(yaxis=dict(range=[0, ymax])))


    def update_plot(self, name, x, y):
        # Create plot if not registered
        try:
            plot_d = self.windows[name]
        except:
            warnings.warn("Plot not found, creating new plot")
            plot_d = {"xlabel":"X", "ylabel":"Y", "plot_type":"scatter"}

        plotter = self.viz.scatter if plot_d["plot_type"] == "scatter" else self.viz.line

        # WHY WAS "Y" A NESTED LIST???
        #data = {"X": np.asarray(x), "Y": np.asarray([y])} if plot_d["plot_type"] == "line" else {"X": np.asarray([x, y])}

        data = {"X": np.asarray(x), "Y": np.asarray(y)} if plot_d["plot_type"] == "line" else {"X": np.asarray([x, y])}

        ## Update plot
        if "plot" in plot_d.keys():
            plotter(
                **data,
                win=plot_d["plot"],
                update="append"
            )
        else: # Create new plot
            win = plotter(
                **data,
                opts=plot_d["opts"]
            )
            plot_d["plot"] = win
            self.windows["name"] = plot_d

    # LOADING
    def load_log(self, path):
        self.viz.replay_log(path)

    def load_all_env(self, root, keyword="visdom"):
        for d, ss, fs in os.walk(root):
            for f in fs:
                full_env = os.path.join(d, f)
                # Don't load "BSF" graphs, just complete graphs
                if full_env[-5:]==".json" and keyword in full_env and f != "losses.json" and "BSF_" not in full_env:
                    print("Loading {}".format(full_env))
                    self.viz.replay_log(full_env) # viz.load load the environment to viz

    def save_env(self, file_path=None, current_env=None, new_env=None):
        if file_path is None:
            file_path = os.path.join(self.config["results_dir"], "visdom.json")
        if current_env is None:
            current_env = self.env_name
            
        new_env = current_env if new_env is None else new_env
        #self.viz = Visdom(env=current_env) # get current env
        data = json.loads(self.viz.get_window_data())
        if len(data) == 0:
            print("NOTHING HAS BEEN SAVED: NOTHING IN THIS ENV - DOES IT EXIST ?")
            return
    
        file = open(file_path, 'w+')
        for datapoint in data.values():
            output = {
                'win': datapoint['id'],
                'eid': new_env,
                'opts': {}
            }
    
            if datapoint['type'] != "plot":
                output['data'] = [{'content': datapoint['content'], 'type': datapoint['type']}]
                if datapoint['height'] is not None:
                    output['opts']['height'] = datapoint['height']
                if datapoint['width'] is not None:
                    output['opts']['width'] = datapoint['width']
            else:
                output['data'] = datapoint['content']["data"]
                output['layout'] = datapoint['content']["layout"]
    
            to_write = json.dumps(["events", output])
            file.write(to_write + '\n')
        file.close()

def initialize_visdom(env_name, config):
    if not config["use_visdom"]:
        return
    try:
        config["visdom_manager"] = Plot("Loss", env_name=env_name, config=config)
        return config["visdom_manager"]
    except:
        config["use_visdom"] = False
        config["logger"].warning("Unable to initialize visdom, is the visdom server started?")

def plot_all(config):
    """
    ADD SMOOTHING
    Args:
        config:

    Returns:

    """
    if not config["use_visdom"]:
        return

    visdom_manager = config["visdom_manager"]
    for title, stat in config["stats"].items():
        if isinstance(stat, Stat) and stat.plot and stat.updated_since_plot:
            #print("updating {}".format(stat.name), stat.x, stat.y)
            visdom_manager.update_plot(stat.name, stat.x[-stat.plot_update_length:], stat.y[-stat.plot_update_length:])
            stat.updated_since_plot = False

def test():
    plot = Plot("Test")
    plot.register_scatterplot("Loss", "Epoch", "Loss")

    for i in range(0,10):
        plot.update_plot("Loss", i, 2)

def close_all_env(plotter):
    for env in plotter.viz.get_env_list():
        plotter.viz.delete_env(env)

def load_all(path, key='test_cer', clear=True, keyword=""):
    # python -m visdom.server -p 8080
    plotter = Plot("NewEnv")
    close_all_env(plotter)

    for p in Path(path).rglob("losses.json"):
        if "BSF" not in p.as_uri() and keyword in p.as_uri():
            print(p)
            name = p.parent.name.replace("-", "_")
            name = name.split("_")
            #name = "_".join((name[0],name[2],name[3],name[4], name[1]))
            name = "_".join((name[2], name[3], name[0]))
            print(name)
            plotter = Plot(name)
            losses = json.loads(p.read_text())[key]
            x = list(range(len(losses)))
            plotter.register_plot(key, "Epoch", key, plot_type="line", ymax=.1)
            plotter.update_plot(key, x, losses)





if __name__=="__main__":
    # python -m visdom.server -p 8080
    path = r"/media/data/GitHub/simple_hwr/results/occlusion/online_or_offline_only/variants/"
    path = r"/media/SuperComputerGroups/fslg_hwr/taylor_simple_hwr/results/occlusion/online_or_offline_only"
    path = r"/media/SuperComputerGroups/fslg_hwr/taylor_simple_hwr/results/occlusion/online_or_offline_only"
    path = r"/home/taylor/shares/Super/SuperComputerGroups/fslg_hwr/taylor_simple_hwr/results/occlusion"
    load_all(path, keyword="20190920")
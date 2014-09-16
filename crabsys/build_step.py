
from os.path import join as pjoin
from utils import system_command

class BuildStep:
    def __init__(self, build_step_info, context):
        self.context = context

        self.directory = build_step_info.get("directory", "")
        self.params = build_step_info.get("params", [])

        if "command" not in build_step_info:
            raise Exception("A command requires a 'command' attribute!")

        self.command = build_step_info.get("command")

    def run(self):
        (retcode, stdout, stderr) = system_command([self.command]+self.params, pjoin(self.context.current_dir, self.directory))
        if retcode != 0:
            print stderr
            raise Exception("Command returned non-zero code: %s" % (self.command))


def parseListOfBuildSteps(build_steps_info, context, attribute=None):
    if attribute:
        build_steps_info = build_steps_info.get(attribute, [])

    return [BuildStep(info, context) for info in build_steps_info]

# Solver configuration

These YAML files describe the configuration of each solver.
These are used by the `smt-runner` infrastructure to run
the experiments.

These files are the "generic" variants of the solver
configurations in `../mars` that aren't specific to
the mars machine and can be used to reproduce
experiments on another machine.

NOTE: If you want to reproduce experiments more acurately
you need to use CPU-pinning and memory set pinning.

You can do this by adding the following the YAML to the solver configuration
YAML file and then customising it to the CPU arrangement of your machine.

```
backend:
  name: "Docker"
  config:
      resource_pinning:
        # mars has 16 real CPU cores.
        # systemd should be configured that init is pinned to cpus 0 and 2.
        # To do this add `CPUAffinity=0 2` to `/etc/systemd/system.conf`.
        # You should also disable hyperthreading.
        #
        # This leaves cpus 1,3-15 free for our jobs. Don't use 1 to try to reduce load
        cpu_ids: [ 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] # Max 13 jobs possible
        cpus_per_job: 1 # each solver run gets a single cpu
        # make sure each job only uses the nearest numa memset to try to avoid
        # noise created by memory latency.
        use_memset_of_nearest_node: true
```

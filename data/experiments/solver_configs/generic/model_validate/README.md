# JFS Model validation configs

These are variants of the JFS solver configurations that enable
model generation and validation. Both are usually off by default.

Model generation is the process of reading a fuzzer found input and
turning it into a model (a constant assignment to each free variable
in the original constraints).

Model validation is the process of taking the generated model
and substituting the assignments in the model into the original
constraints. If the model is correct then every constraint should
evaluate to the constant true. If this is not the case then model
validation fails.

# zBEMT Documentation

This page is the GitHub-native entry point for the current zBEMT implementation. The complete application manual is [documentation.html](documentation.html). The binding software behavior is defined in [software_requirements.md](software_requirements.md), and the physics evidence is recorded in [physics_verification_report.md](physics_verification_report.md).

## Current implementation

| Area | Implemented behavior | Execution path |
| --- | --- | --- |
| Annular inflow | Glauert local | Run Case, batch, Python API |
| Skewed-wake inflow | Coleman local/global, Coleman-Feingold global, Drees local/global | Run Case, batch, Python API |
| Finite-state inflow | Pitt-Peters steady | Run Case, batch, Python API |
| Unsteady finite-state inflow | Pitt-Peters three-state time march | Transient Simulation and maneuver API |
| Losses and section aerodynamics | Prandtl tip/root loss, compressibility, reverse-flow treatment, full-range polar extension | Steady and transient aerodynamic evaluations |
| Rotational/radial-flow corrections | Himmelskamp/Snel rotational augmentation and 3D radial-flow drag resolution | Config/Engine |
| Dynamic stall | Øye frequency-domain approximation and time march | Run Case or Transient Simulation, according to method |
| Blade motion | Periodic rigid-body flap and optional lead-lag with offset/spring terms and pitch-flap coupling | Geometry blade dynamics |
| Transient blade motion | Flap is updated quasi-steadily at each maneuver sample | Transient Simulation |

There is no distinct Glauert-global wake model. Legacy configuration values with that name migrate to the axisymmetric Glauert-local model. The unsteady Pitt-Peters model is not an isolated steady Run Case. It is a state march along a maneuver.

## Johnson cross-check

The blade-dynamics and wake conventions were checked against Wayne Johnson, *Rotorcraft Aeromechanics* (Cambridge University Press, 2013). The most relevant sections are 5.2.2, 6.15, 6.18, 16.8.2, and 19.1.1.

### Flap frequency and damping

For the implemented uniform rigid blade with flap-hinge offset $e$ and a root spring,

$$
\nu_\beta^2
=
1+\frac{3}{2}\frac{e}{1-e}
+\frac{K_\beta}{I_\beta\Omega^2}.
$$

The scalar aerodynamic damping used by the harmonic balance is the exact integral of the implemented mean-damping approximation for the actual-hinge coordinate,

$$
d_\beta
=
\frac{\gamma}{2}
\left[
\frac{(1-e)^4}{4}
+
\frac{e(1-e)^3}{3}
\right].
$$

At $e=0$, this reduces to $d_\beta=\gamma/8$, the classical centrally hinged result.

For harmonic $n$, the code solves

$$
\begin{bmatrix}
\nu_\beta^2-n^2 & n d_\beta \\
-n d_\beta & \nu_\beta^2-n^2
\end{bmatrix}
\begin{bmatrix}
\beta_{nc} \\
\beta_{ns}
\end{bmatrix}
=
\begin{bmatrix}
M_{nc} \\
M_{ns}
\end{bmatrix}.
$$

Its determinant is

$$
(\nu_\beta^2-n^2)^2+(n d_\beta)^2.
$$

Therefore $\nu_\beta=n$ is not singular when damping is finite. This matters for a centrally hinged articulated rotor: its structural flap frequency is 1/rev, while aerodynamic damping keeps the periodic 1/rev response finite. Validation and the solver use the full damped operator.

### Hinge angle and tip-path-plane angle

zBEMT uses the actual rotation about the flap hinge internally:

$$
z(r)=(r-eR)\,\beta_{hinge}.
$$

Johnson also presents the equivalent tip-normalized mode shape. In the small-angle model, the corresponding shaft-to-tip angle is

$$
\beta_{TPP}\simeq(1-e)\,\beta_{hinge}.
$$

The exported `beta_*` values remain the internal hinge coordinate. The exported `tpp_tilt_*` values apply the $(1-e)$ scale and the project's tilt sign convention.

The Lock-number input uses the same actual-hinge normalization as the internal inertia. If a reference gives Johnson's tip-normalized modal Lock number, use

$
\gamma_{hinge}=\frac{\gamma_{tip}}{(1-e)^2}.
$

At zero hinge offset the two definitions coincide.

### Pitch-flap coupling

Positive delta-three coupling follows

$$
\Delta\theta=-\tan(\delta_3)\,\beta.
$$

Flap-up therefore decreases pitch. This is a restoring aerodynamic stiffness, not an additional damping term.

### Skewed inflow

The empirical Coleman and Drees implementations use a linear first-harmonic induced-velocity field over the disk. Coleman-Feingold is kept as a separate global convention so its coefficient law is not confused with the other Coleman formulation. Pitt-Peters instead solves a three-state finite-state disk model.

### Radial drag

When radial-flow drag is enabled, the section drag is resolved along the true three-dimensional relative-velocity vector. The radial component contributes to in-plane hub force but does not create direct shaft torque or shaft power.

## Known model boundaries

- The flap harmonic balance uses a scalar mean aerodynamic damping term based on the representative chord and $U_T=\Omega r$. It does not assemble Johnson's full periodic forward-flight damping matrix.
- The lead-lag oscillator does not include flap-lag Coriolis coupling. Do not use it as a ground-resonance or coupled flap-lag stability model.
- Pitt-Peters is a linear finite-state inflow theory. The solver reports when local total inflow reverses over part of the disk instead of hiding that condition.
- Transient flapping is quasi-steady at each maneuver sample. zBEMT does not integrate a structural flap state in time.
- Himmelskamp/Snel and the radial-flow treatment are engineering corrections. They do not replace a three-dimensional viscous rotor CFD solution.
- Full-range polar extension is a model outside the measured or generated polar range. Results in deep reverse flow remain model-dependent.

## Documentation map

- [Root README](../README.md): installation, first run, major capabilities, and test commands.
- [Complete application manual](documentation.html): every GUI field, equation, workflow, and CLI/`.bemt` mapping.
- [Software requirements](software_requirements.md): binding behavioral requirements and numerical guards.
- [Physics verification report](physics_verification_report.md): evidence campaign, corrected defects, and declared limitations.
- [Physics evidence closure plan](physics_evidence_closure_plan.md): evidence ownership and closure process.

## Verification commands

Run the complete test suite with:

```bash
python tests/run_all_tests.py
```

Run the physics evidence campaign with:

```bash
python tools/run_quality_checks.py --suite physics
```

Check every saved project configuration with:

```bash
python tools/check_project_configs.py
```

The CI workflow runs the engine suite across supported Python versions, the complete GUI suite, and the installation check for pull requests.

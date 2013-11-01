#!/usr/bin/env python
# encoding: utf-8
r"""
Solitary wave formation in periodic nonlinear elastic media
===========================================================

Solve a one-dimensional nonlinear elasticity system:

.. math::
    \epsilon_t + u_x & = 0 \\
    (\rho(x) u)_t + \sigma(\epsilon,x)_x & = 0.

Here :math:`\epsilon` is the strain, :math:`\sigma` is the stress, 
u is the velocity, and :math:`\rho(x)` is the density.  
We take the stress-strain relation :math:`\sigma = e^{K(x)\epsilon}-1`;
:math:`K(x)` is the linearized bulk modulus.
Note that the density and bulk modulus may depend explicitly on x.

The problem solved here is based on [LeVYon03]_.  An initial hump
evolves into two trains of solitary waves.

"""
import numpy as np


def qinit(state,ic=2,a2=1.0,xupper=600.):
    x = state.grid.x.centers
    
    if ic==1: #Zero ic
        state.q[:,:] = 0.
    elif ic==2:
        # Gaussian
        sigma = a2*np.exp(-((x-xupper/2.)/10.)**2.)
        state.q[0,:] = np.log(sigma+1.)/state.aux[1,:]
        state.q[1,:] = 0.


def setaux(x,rhoB=4,KB=4,rhoA=1,KA=1,alpha=0.5,xlower=0.,xupper=600.,bc=2):
    aux = np.empty([3,len(x)],order='F')
    xfrac = x-np.floor(x)
    #Density:
    aux[0,:] = rhoA*(xfrac<alpha)+rhoB*(xfrac>=alpha)
    #Bulk modulus:
    aux[1,:] = KA  *(xfrac<alpha)+KB  *(xfrac>=alpha)
    aux[2,:] = 0. # not used
    return aux

    
def b4step(solver,state):
    #Reverse velocity at trtime
    #Note that trtime should be an output point
    if state.t>=state.problem_data['trtime']-1.e-10 and not state.problem_data['trdone']:
        #print 'Time reversing'
        state.q[1,:]=-state.q[1,:]
        state.q=state.q
        state.problem_data['trdone']=True
        if state.t>state.problem_data['trtime']:
            print 'WARNING: trtime is '+str(state.problem_data['trtime'])+\
                ' but velocities reversed at time '+str(state.t)
    #Change to periodic BCs after initial pulse 
    if state.t>5*state.problem_data['tw1'] and solver.bc_lower[0]==0:
        solver.bc_lower[0]=2
        solver.bc_upper[0]=2


def zero_bc(state,dim,t,qbc,num_ghost):
    """Set everything to zero"""
    if dim.on_upper_boundary:
        qbc[:,-num_ghost:]=0.

def moving_wall_bc(state,dim,t,qbc,num_ghost):
    """Initial pulse generated at left boundary by prescribed motion"""
    if dim.on_lower_boundary:
        qbc[0,:num_ghost]=qbc[0,num_ghost] 
        t=state.t; t1=state.problem_data['t1']; tw1=state.problem_data['tw1']
        a1=state.problem_data['a1'];
        t0 = (t-t1)/tw1
        if abs(t0)<=1.: vwall = -a1*(1.+np.cos(t0*np.pi))
        else: vwall=0.
        for ibc in xrange(num_ghost-1):
            qbc[1,num_ghost-ibc-1] = 2*vwall*state.aux[1,ibc] - qbc[1,num_ghost+ibc]



def setup(use_petsc=0,kernel_language='Fortran',solver_type='classic',outdir='./_output'):
    """
    Stegoton problem.
    Nonlinear elasticity in periodic medium.
    See LeVeque & Yong (2003).

    $$\\epsilon_t - u_x = 0$$
    $$\\rho(x) u_t - \\sigma(\\epsilon,x)_x = 0$$
    """
    from clawpack import riemann

    if use_petsc:
        import clawpack.petclaw as pyclaw
    else:
        from clawpack import pyclaw

    if kernel_language=='Python':
        rs = riemann.nonlinear_elasticity_1D_py.nonlinear_elasticity_1D
    elif kernel_language=='Fortran':
        rs = riemann.nonlinear_elasticity_fwave_1D

    if solver_type=='sharpclaw':
        solver = pyclaw.SharpClawSolver1D(rs)
        solver.char_decomp=0
    else:
        solver = pyclaw.ClawSolver1D(rs)

    solver.kernel_language = kernel_language

    solver.bc_lower[0] = pyclaw.BC.periodic
    solver.bc_upper[0] = pyclaw.BC.periodic

    #Use the same BCs for the aux array
    solver.aux_bc_lower = solver.bc_lower
    solver.aux_bc_upper = solver.bc_upper

    xlower=0.0; xupper=600.0
    cellsperlayer=6; mx=int(round(xupper-xlower))*cellsperlayer
    x = pyclaw.Dimension('x',xlower,xupper,mx)
    domain = pyclaw.Domain(x)
    state = pyclaw.State(domain,solver.num_eqn)

    #Set global parameters
    alpha = 0.5
    KA    = 1.0
    KB    = 4.0
    rhoA  = 1.0
    rhoB  = 4.0
    state.problem_data = {}
    state.problem_data['t1']    = 10.0
    state.problem_data['tw1']   = 10.0
    state.problem_data['a1']    = 0.0
    state.problem_data['alpha'] = alpha
    state.problem_data['KA'] = KA
    state.problem_data['KB'] = KB
    state.problem_data['rhoA'] = rhoA
    state.problem_data['rhoB'] = rhoB
    state.problem_data['trtime'] = 250.0
    state.problem_data['trdone'] = False

    #Initialize q and aux
    xc=state.grid.x.centers
    state.aux=setaux(xc,rhoB,KB,rhoA,KA,alpha,xlower=xlower,xupper=xupper)
    qinit(state,ic=2,a2=1.0,xupper=xupper)

    tfinal=500.; num_output_times = 10;

    solver.max_steps = 5000000
    solver.fwave = True 
    solver.before_step = b4step 
    solver.user_bc_lower=moving_wall_bc
    solver.user_bc_upper=zero_bc

    claw = pyclaw.Controller()
    claw.keep_copy = False
    claw.output_style = 1
    claw.num_output_times = num_output_times
    claw.tfinal = tfinal
    claw.solution = pyclaw.Solution(state,domain)
    claw.solver = solver

    return claw


if __name__=="__main__":
    from clawpack.pyclaw.util import run_app_from_main
    output = run_app_from_main(setup)
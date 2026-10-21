#!/usr/bin/env python3


"""
This script aims to 'simulate' heat transfer inside a mesh / matrix of nodes
considering a border initial value.
The formulation is based on partial diferential equations transformed into
algebric equations or systems, through finite differences method;
"""


import sympy as sp
import numpy as np
import gmsh
import time
from math import isclose
from collections import Counter
from typing import Union


'''gmsh.initialize()
gmsh.model.add("Model")
build = gmsh.model.geo'''


np.set_printoptions(precision=1, suppress=True)


def mesh(shape: Union[tuple, list], value: Union[float, int]) -> np.array:
    """
    Description:
        Generates a quadrilateral array filled with 0 values with shape a, b
    Parameters:
        shape - Lines, Columns
        value - Initial value
    """
    return np.full(shape, value, dtype=float)


def boundary_conditions(matrix: np.array,
                        boundary: str, 
                        value: Union[float, int]) -> np.array:
    """
    Description:
        Creates a mask with boundary condition
    Parameters:
        shape - Lines, Columns;
        boundary - 1 (top); 2 (left), 3 (right); 4 (bottom);
        value - Numerical value for boundary condition
    """
    a, b = matrix.shape

    if isclose(boundary, 1):
        top_line = np.full(b, value)
        return np.insert(arr=matrix, obj=0, values=top_line, axis=0)
    
    elif isclose(boundary, 2):
        left_column = np.full(a, value)
        return np.insert(arr=matrix, obj=0, values=left_column, axis=1)
    
    elif isclose(boundary, 3):
        right_column = np.full(a, value)
        return np.insert(arr=matrix, obj=b, values=right_column, axis=1)
    
    elif isclose(boundary, 4):
        bottom_line = np.full(b, value)
        return np.append(arr=matrix, values=bottom_line, axis=0)


def iteractive_method(matrix: np.array,
                      shape: Union[tuple, list],
                      alpha: Union[int, float],
                      spacing_geo: Union[int, float]=0.1,
                      spacing_time: Union[int, float]=1e-2) -> np.array:
    """
    Description:
        Consider a bidimensional mesh, which each node has a number
        A Taylor series define temperatures on nodes (M+1, N), (M-1, N),
        (M, N+1) and (M, N-1) in terms of its central node (M, N) value.
            T(M+1, N) = T(M, N) + dT/dx . Δx + d²T/dx² . Δx²/2! + O(Δx³)    [I]
            T(M-1, N) = T(M, N) - dT/dx . Δx - d²T/dx² . Δx²/2! + O(Δx³)    [II]
            T(M, N+1) = T(M, N) + dT/dy . Δy + d²T/dy² . Δy²/2! + O(Δy³)    [III]
            T(M, N-1) = T(M, N) - dT/dy . Δy - d²T/dy² . Δy²/2! + O(Δy³)    [IV]
            where T refers to temperature field
        
        Δx² and Δy² are vary low values, we can ignore it
        So, it's possible to continue with:
            for node (M+1/2, N)
                dT/dx ~ (T(M+1, N) - T(M, N)) / Δx  [V]
            for node (M-1/2, N)
                dT/dx ~ (T(M, N) - T(M-1, N)) / Δx  [VI]
            for node (M, N+1/2)
                dT/dx ~ (T(M, N+1) - T(M, N)) / Δy  [VII]
            for node (M, N-1/2)
                dT/dx ~ (T(M, N) - T(M, N-1)) / Δy  [VIII]
        
        Calculating derivative 2nd
            d²T/dx² ~ (dT/dx(M+1/2, N) - dT/dx(M-1/2, N)) / Δx
                    ~ (T(M+1, N) + T(M-1, N) - 2 . T(M, N)) / Δx²   [IX]
            d²T/dy² ~ (dT/dx(M, N+1/2) - dT/dx(M, N-1/2)) / Δy
                    ~ (T(M, N+1) + T(M, N-1) - 2 . T(M, N)) / Δy²   [X]
        
        In time history...
            dT/dt(M, N) ~ (T(M, N)[p+1] - T(M, N)[p]) / Δt  [XI]
            where   p refers to a previous time and p+1 refers to actual time  
                    t refers to the time variable  
    
        Lets look to the PDE below
            (1/α) . dT/dt = d²T/dx² + d²T/dy²   [XII]
            where α is the thermal difusivity:
                α = k / (p . Cp)    [XIII]
                where:  p is the specific mass (density) of the continuous medium
                        Cp is the specific heat at constant pressure
                        k is the thermal conductivity of the medium

        Once [IX] to [XI] were calculated, it's possible to descritize [XII] as:
            (1/α) . (T(M, N)[p+1] - T(M, N)[p]) / Δt = \
                (T(M+1, N)[p] + T(M-1, N)[p] - 2 . T(M, N)[p]) / Δx² \
                    + (T(M, N+1)[p] + T(M, N-1)[p] - 2 . T(M, N)[p]) / Δy²    [XIII]

        If we isolate term T(M, N)[p+1]...
            T(M, N)[p+1] = \
                Fo . (T(M+1, N)[p] + T(M-1, N)[p] + T(M, N+1)[p] + T(M, N-1)[p]) \
                    + (1 - 4 . Fo) . T(M, N)[p]  [XIV]
            where   Fo is Fourier number:
                Fo = α . Δt / Δx²   [XV]
        
        With equation [XIV], in a stationary medium, is possible to define, for
        actual time (p+1), a node temperature based on its neighbours temperature
        on a previous time (p)
    """
    t_i = 0
    converged = False
    a, b = matrix.shape

    # as boundary conditions are appended to the matrix, we need to reconsider
    # the shape limits to iterate lines and columns correctly
    if a > shape[0]:
        l_i, l_f, boundary_condition = (
            (1, a-1, 'top') if (matrix[0] != matrix[1]).all() 
            else (0, a-2, 'bottom')
            )
        c_i, c_f = 0, b-1

    elif b > shape[1]:
        l_i, l_f = 0, a-1
        c_i, c_f, boundary_condition = (
            (1, b-1, 'left') if (matrix[:, 0] != matrix[:, 1]).all() 
            else (0, b-2, 'right')
            )

    Fo = alpha * 10e-6 * spacing_time / (spacing_geo ** 2)

    # e - Top side neighbour, r - Bottom side neighbour
    # t - Right side neighbour, y - Left side neighbour
    # u - node itself
    e, r, t, y, u = sp.symbols('e r t y u')
    expr = Fo * sum([e, r, t, y]) + (1 - 4 * Fo) * u

    while not converged:

        A_p = A.copy()

        for m in range(l_i, l_f+1):
            for n in range(c_i, c_f+1):

                if isclose(m, l_i) and isclose(n, c_i):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n] if boundary_condition == 'top' else 0,
                        r: A_p[m+1, n],
                        t: A_p[m, n+1],
                        y: A_p[m, n-1] if boundary_condition == 'left' else 0,
                        u: A_p[m, n]
                    })

                elif isclose(m, l_f) and isclose(n, c_f):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n] if boundary_condition == 'bottom' else 0,
                        t: A_p[m, n+1] if boundary_condition == 'right' else 0,
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })

                elif isclose(m, l_i) and isclose(n, c_f):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n] if boundary_condition == 'top' else 0,
                        r: A_p[m+1, n],
                        t: A_p[m, n+1] if boundary_condition == 'right' else 0,
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })

                elif isclose(m, l_f) and isclose(n, c_i):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n] if boundary_condition == "bottom" else 0,
                        t: A_p[m, n+1],
                        y: A_p[m, n-1] if boundary_condition == "left" else 0,
                        u: A_p[m, n]
                    })
                
                elif isclose(m, l_i):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n] if boundary_condition == 'top' else 0,
                        r: A_p[m+1, n],
                        t: A_p[m, n+1],
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })
                    
                elif isclose(n, c_i):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n],
                        t: A_p[m, n+1],
                        y: A_p[m, n-1] if boundary_condition == 'left' else 0,
                        u: A_p[m, n]
                    })
                    
                elif isclose(m, l_f):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n] if boundary_condition == 'bottom' else 0,
                        t: A_p[m, n+1],
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })
                    
                elif isclose(n, c_f):
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n],
                        t: A_p[m, n+1] if boundary_condition == 'right' else 0,
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })
                    
                else:
                    A[m, n] = expr.subs({
                        e: A_p[m-1, n],
                        r: A_p[m+1, n],
                        t: A_p[m, n+1],
                        y: A_p[m, n-1],
                        u: A_p[m, n]
                    })
        
        t_i += 1
        converged = check_convergence(A)

        if t_i % 100 == 0 or converged:
            dt_max = round(np.max(A) - np.min(A), 1)
            print(A)
            print(f"Iter: {t_i} | t: {round(spacing_time * t_i, 1)} s | dt_max: {dt_max} °C")
            print("\n")
            time.sleep(.5)

    return A


def check_convergence(matrix: np.array, adm_error: float=0.5) -> bool:
    """
    Description:
        Iterates matrix lines and columns verifying if there's any value changing
        between a node and its neighbours major than adm_error
        If that condition is achieved, set convergence value to False
        Otherwise, set convergence value to True
    """
    a, b = matrix.shape

    for i in range(a):
        for j in range(b):
            if isclose(i, 0) and isclose(j, 0):
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j+1]) > adm_error
                ])
            elif isclose(i, a) and isclose(j, b):
                return any([
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            elif isclose(i, 0) and isclose(j, b):
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            elif isclose(i, a) and isclose(j, 0):
                return any([
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            elif isclose(i, 0):
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j+1]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            elif isclose(j, 0):
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j+1]) > adm_error
                ])
            elif isclose(i, a):
                return any([
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j+1]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            elif isclose(j, b):
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])
            else:
                return any([
                    abs(matrix[i, j] - matrix[i+1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i-1, j]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j+1]) > adm_error,
                    abs(matrix[i, j] - matrix[i, j-1]) > adm_error
                ])

    return True


'''
Boundaries:     1 - top;        2 - left;       3 - right;      4 - bottom

α = [
    150 * 10e-6 m²/s for silver,
    115 * 10e-6 m²/s for copper,
    95 * 10e-6 m²/s for aluminum,
    22 * 10e-6 m²/s for steel,
    1.25 * 10e-6 m²/s for marble,
    0.75 * 10e-6 m²/s for concrete,
    0.4 * 10e-6 m²/s for glass,
    0.14 * 10e-6 m²/s for water,
    0.13 * 10e-6 m²/s for wood,
    0.54 * 10e-6 m²/s for ice,
    0.15 * 10e-6 m²/s for polyethylene,
    0.2 * 10e-6 m²/s for nylon,
    20 * 10e-6 m²/s for air
]
'''


if __name__ == "__main__":

    # Test 1
    # Matrix 5x6
    # Boundary condition: 100 °C top boundary
    # Initial value: 0 °C

    shape = (5, 6)
    A = mesh(shape, value=0)
    A = boundary_conditions(A, boundary=3, value=100)

    A = iteractive_method(A, shape, alpha=150)


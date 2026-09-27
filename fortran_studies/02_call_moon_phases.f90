! a main program to calling and testing moon_phases subroutine
! 
! 
! 
! 

PROGRAM call_moon_phases

    USE moon_phases_mod, ONLY: moon_phases

    IMPLICIT NONE

    integer, PARAMETER :: dp = kind(1.0d0)

    INTEGER :: julian_day, n_phase, type_phase
    REAL(dp)    :: frac_day

    ! Calculates the Julian day of the 1500th new moon since January 1900.
    n_phase    = 1500
    type_phase = 0

    CALL moon_phases(n_phase, type_phase, julian_day, frac_day)

    PRINT *, "Julian Day:", julian_day
    PRINT *, "Hours of the day:", frac_day

END PROGRAM call_moon_phases


! Run in the CMD: 
! gfortran 01_moon_phases.f90 02_call_moon_phases.f90 -o 02_call_moon_phases


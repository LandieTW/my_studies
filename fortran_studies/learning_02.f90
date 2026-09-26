!
! 
! 
! 
! 

PROGRAM main
    IMPLICIT NONE

    INTEGER :: julian_day, n_phase, type_phase
    REAL    :: frac_day

    ! Calculates the Julian day of the 1500th new moon since January 1900.
    n_phase    = 1500
    type_phase = 0

    CALL moon_phases(n_phase, type_phase, julian_day, frac_day)

    PRINT *, "Julian Day:", julian_day
    PRINT *, "Hours of the day:", frac_day

END PROGRAM main


! Run in the PowerShell: 
! "& "C:\fortran\mingw64\bin\gfortran.EXE" -ffree-form -Wall learning_02.f90 learning_01.f90 -o lunar.exe"

! & "C:\fortran\mingw64\bin\gfortran.EXE" ->    executes the gfortran compiler
! -ffree-form ->                                tells the compiler that the source code is in free format (f90)
! -Wall ->                                      enables all compiler's warning messages
! learning_02.f90 learning_01.f90 ->            the source files to compile


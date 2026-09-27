! a main program to calling and testing julian day function
!
!
!
!

program test_julian_day

    use julian_day_mod, only: julian_day

    implicit none

    print *, "1/1/2000   ->", julian_day(1, 1, 2000)
    print *, "15/10/1582 ->", julian_day(10, 15, 1582)
    print *, "1/1/1900   ->", julian_day(1, 1, 1900)

end program test_julian_day


! Run in the CMD: 
! gfortran 03_julian_day.f90 04_test_julian_day.f90 -o 04_test_julian_day


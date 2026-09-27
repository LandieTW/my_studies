! Finding the date of a Friday 13th on which the moon was full
! (getting all other fridays 13th as a by-product)
!
!
!

program bad_luck

    use moon_phases_mod, only: moon_phases
    use julian_day_mod, only: julian_day

    implicit none

    integer, PARAMETER :: dp = KIND(1.0d0)              ! Avoid precision errors
    real(dp), PARAMETER :: TIMZON = -5.0_dp / 24.0_dp   ! Time zone -5 is Eastern Standard Time
    integer, PARAMETER :: iybeg = 1900, iyend = 2000

    integer :: ic, icon, idwk, ifrac, im, iyyy, jd, jday, n
    real(dp) :: frac

    write (*,'(1x, a, i5, a, i5)') &
        'Full moons on Friday the 13th from', iybeg, ' to', iyend

    do iyyy = iybeg, iyend                      ! Loop over each year,
        do im = 1, 12                           ! and each month

            jday = julian_day(im, 13, iyyy)     ! Is the 13th a Friday?
            idwk = MOD(jday + 1, 7)

            if (idwk /= 5) cycle
            ! This value n is a first approximation to how many full moons have occurred  since 1900
            ! We will feed it into the phase routine and adjust it up or down until we determine that our desired 13th was or was not a full moon.
            ! The variable icon signals the direction of adjustment.
            n = INT(12.37_dp * (iyyy - 1900 + (im - 0.5_dp) / 12.0_dp))
            icon = 0
            
            do  ! moon (bracket) loop adjustment
                call moon_phases(n, 2, jd, frac)                ! Get data of full moon n
                ifrac = NINT(24.0_dp * (frac + TIMZON))         ! Convert to hours in correct time zone
                
                if (ifrac < 0) then                 ! convert from Julian Days beginning at moon
                    jd = jd - 1                     ! to civil days beginning at midnight
                    ifrac = ifrac + 24
                end if

                if (ifrac > 12) then
                    jd = jd + 1
                    ifrac = ifrac - 12
                else
                    ifrac = ifrac + 12
                end if

                if (jd == jday) then              ! Did we hit our target day?
                    write (*,'(/1x, i2, a, i2, a, i4/)') im, '/', 13, '/', iyyy
                    write (*, '(1x, a, i2, a)') &
                        'Full moon ', ifrac, ' hrs after midnight (EST).'
                    exit    ! Part of the brack-structure, case of a match
                end if      ! Didn't hit it

                ic = ISIGN(1, jday-jd)
                if (ic == -icon) exit     ! another brak, case of no match
                icon = ic
                n = n + ic

            end do
        end do
    end do
end program bad_luck


! Run in the CMD: 
! gfortran -c 01_moon_phases.f90
! gfortran -c 03_julian_day.f90
! gfortran 01_moon_phases.o 03_julian_day.o 05_bad_luck.f90 -o 05_bad_luck


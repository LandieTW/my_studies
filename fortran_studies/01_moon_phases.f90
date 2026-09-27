! This routine calculates the phases of the moon.
! Given an integer 'n_phase' and a code 'type_phase' for the phase desired
! (0 for new moon, 1 for first quarter, 2 for full moon, and 3 for last quarter),
! Routine returns Julian Day Number 'julian_day', and fractional part of a day 'frac_day' to be added to it, of the 'type_phase' such phase since  January, 1900.
! Greenwich Mean Time is assumed.

module moon_phases_mod
    implicit none
    private
    public :: moon_phases
    integer, PARAMETER :: dp = kind(1.0d0)
contains
    subroutine moon_phases(n_phase, type_phase, julian_day, frac_day)

        implicit none

        integer, intent(IN)  :: n_phase, type_phase
        integer, intent(OUT) :: julian_day
        real(dp), intent(OUT) :: frac_day

        real, PARAMETER :: RAD = 3.14159265 / 180.
        integer, PARAMETER :: REF_DAY = 2415020   ! Julian date on 1 Jan 1900, 12:00 UT

        integer :: i
        real :: moon_mean_anomaly, sun_mean_anomaly, moon_cycle, t, t_squared, frac_day_accum

        ! calculation from "Astronomical algorithms", by Jean Meeus, page 350

        moon_cycle = n_phase + type_phase / 4.
        t = moon_cycle / 1236.85
        t_squared = t ** 2

        moon_mean_anomaly = 359.2242 + 29.105356 * moon_cycle
        sun_mean_anomaly  = 306.0253 + 385.816918 * moon_cycle + 0.010730 * t_squared

        julian_day    = REF_DAY + 28 * n_phase + 7 * type_phase
        frac_day_accum = 0.75933 + 1.53058868 * moon_cycle + (1.178e-4 - 1.55e-7 * t) * t_squared

        if (type_phase == 0 .OR. type_phase == 2) THEN

            frac_day_accum = frac_day_accum &
                + (0.1734 - 3.93e-4 * t) * SIN(RAD * sun_mean_anomaly) &
                - 0.4068 * SIN(RAD * moon_mean_anomaly)

        else if (type_phase == 1 .OR. type_phase == 3) THEN

            frac_day_accum = frac_day_accum &
                + (0.1721 - 4.e-4 * t) * SIN(RAD * sun_mean_anomaly) &
                - 0.6280 * SIN(RAD * moon_mean_anomaly)

        else
            
            stop 'type_phase invalido: use 0, 1, 2 ou 3'

        end if

        i = INT(frac_day_accum)
        if (frac_day_accum < 0) i = i - 1

        julian_day = julian_day + i
        frac_day   = frac_day_accum - i

    end subroutine moon_phases
end module moon_phases_mod


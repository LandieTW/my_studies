! By its looping over the months and years, the program badluck avoids using any algorithm for converting a Julian Day Number back into a calendar date.
! This routine is not very structuraly interesting, but it is occasionally useful, through doing that.
!
!
!

module calling_date_mod
    implicit none
    private
    public :: calling_date

    integer, parameter :: dp = kind(1.0d0)
    integer, parameter :: IGREG = 2299161   ! Julian day adopted from Gregorian Calendar (10/15/1582)

contains

    subroutine calling_date(julian, mm, id, iyyyy)
        integer, intent(in)  :: julian
        integer, intent(out) :: mm, id, iyyyy
        integer :: ja, jalpha, jb, jc, jd, je

        ! Inverse of the function julian_day.
        ! Here julian is input as a julian day number, and the routine outputs mm, id and iyyy as the month, day and year on which the specified julian day started at noon.

        if (julian >= IGREG) then
            jalpha = int(((julian - 1867216) - 0.25_dp) / 36524.25_dp)      ! Cross-over to Gregorian calendar produces
            ja = julian + 1 + jalpha - int(0.25_dp * jalpha)                ! this correction

        else if (julian < 0) then                                           ! Make day number positive by adding
            ja = julian + 36525 * (1 - julian / 36525)                      ! integer number of julian centuries,
                                                                            ! then subtract them off at the end
        else
            ja = julian
        end if

        jb = ja + 1524
        jc = int(6680.0_dp + ((jb - 2439870) - 122.1_dp) / 365.25_dp)
        jd = 365 * jc + int(0.25_dp * jc)
        je = int((jb - jd) / 30.6001_dp)

        mm = je - 1
        if (mm > 12) mm = mm - 12

        iyyyy = jc - 4715
        if (mm > 2) iyyyy = iyyyy - 1
        if (iyyyy <= 0) iyyyy = iyyyy - 1
        if (julian < 0) iyyyy = iyyyy - 100 * (1 - julian / 36525)

        id = jb - jd - int(30.6001_dp * (je - 1)) + 31
    end subroutine calling_date

end module calling_date_mod


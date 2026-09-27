! julday returns the Julian Day Number that begins at noon of the calendar date specified by month mm, day id, and year iyyy, all integer variables.
! Positive year signifies A.D.;
! Negative, B. C.
! Remember that the year after 1 B. C. was 1 A. D.
! 

module julian_day_mod
    implicit none
    private
    public :: julian_day
contains
    integer function julian_day(mm, id, iyyy) RESULT(jd)

        implicit none

        integer, INTENT(IN) :: mm, id, iyyy

        integer, PARAMETER :: IGREG = 15 + 31 * (10 + 12 * 1582)      ! Gregorian Calendar adpted Oct. 15, 1582

        integer :: ja, jm, jy

        jy = iyyy

        if (jy == 0) stop 'julian_day: there is no year zero'
        
        if (jy < 0) then
            jy = jy + 1
        end if
        
        if (mm > 2) then
            jm = mm + 1
        else
            jy = jy - 1
            jm = mm + 13
        end if

        jd = INT(365.25 * jy) + INT(30.6001 * jm) + id + 1720995

        if (id + 31 * (mm + 12 * iyyy) >= IGREG) then
            ja = INT(0.01 * jy)
            jd = jd + 2 - ja + INT(0.25 * ja)
        end if

    end function julian_day
end module julian_day_mod


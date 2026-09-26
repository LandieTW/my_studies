! julday returns the Julian Day Number that begins at noon of the calendar date specified by month mm, day id, and year iyyy, all integer variables.
! Positive year signifies A.D.;
! Negative, B. C.
! Remember that the year after 1 B. C. was 1 A. D.
! 

INTEGER FUNCTION julday(mm, id, iyyy) RESULT(jd)

    IMPLICIT NONE

    INTEGER, INTENT(IN) :: mm, id, iyyy

    INTEGER, PARAMETER :: IGREG = 15 + 31 * (10 + 12 * 1582)      ! Gregorian Calendar adpted Oct. 15, 1582

    INTEGER :: ja, jm, jy

    jy = iyyy

    IF (jy == 0) STOP 'julday: there is no year zero'
     
    IF (jy < 0) THEN
        jy = jy + 1
    END IF
    
    IF (mm > 2) THEN
        jm = mm + 1
    ELSE
        jy = jy - 1
        jm = mm + 13
    END IF

    jd = INT(365.25 * jy) + INT(30.6001 * jm) + id + 1720995

    IF (id + 31 * (mm + 12 * iyyy) >= IGREG) THEN
        ja = INT(0.01 * jy)
        jd = jd + 2 - ja + INT(0.25 * ja)
    END IF

END FUNCTION julday


PROGRAM test
    IMPLICIT NONE

    INTEGER, EXTERNAL :: julday

    PRINT *, "1/1/2000   ->", julday(1, 1, 2000)
    PRINT *, "15/10/1582 ->", julday(10, 15, 1582)
    PRINT *, "1/1/1900   ->", julday(1, 1, 1900)

END PROGRAM test


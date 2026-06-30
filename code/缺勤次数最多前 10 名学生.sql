SELECT 
    s.student_id,
    s.name,
    s.department,
    COUNT(ar.record_id) AS absent_count
FROM student s
JOIN attendance_record ar ON s.student_id = ar.student_id
WHERE ar.attendance_status = 'absent'
GROUP BY s.student_id, s.name, s.department
ORDER BY absent_count DESC
LIMIT 10;
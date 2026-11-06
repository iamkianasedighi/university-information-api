-- University Information API: fictional demo data (2026 revision)
-- Destructive seed: import into a NEW, disposable database only.

DROP TABLE IF EXISTS ENROLLinfo;
DROP TABLE IF EXISTS CLASSinfo;
DROP TABLE IF EXISTS STDinfo;
DROP TABLE IF EXISTS PROFinfo;

CREATE TABLE PROFinfo (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE STDinfo (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(16) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE CLASSinfo (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    teacher INT NOT NULL,
    CONSTRAINT fk_class_teacher FOREIGN KEY (teacher) REFERENCES PROFinfo(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ENROLLinfo (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    STDid INT NOT NULL,
    CLASSid INT NOT NULL,
    CONSTRAINT uq_student_class UNIQUE (STDid, CLASSid),
    CONSTRAINT fk_enroll_student FOREIGN KEY (STDid) REFERENCES STDinfo(id),
    CONSTRAINT fk_enroll_class FOREIGN KEY (CLASSid) REFERENCES CLASSinfo(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO PROFinfo (id, name) VALUES
(1, 'Dr. Julia Weber'),
(2, 'Dr. Markus Fischer'),
(3, 'Dr. Nina Schubert'),
(4, 'Dr. Tobias Neumann');

-- Phone numbers use the fictional North American 555-01xx range.
INSERT INTO STDinfo (id, name, phone) VALUES
(1, 'Anna Weber', '+12025550100'),
(2, 'Leon Fischer', '+12025550101'),
(3, 'Sara Müller', '+12025550102'),
(4, 'David Becker', '+12025550103'),
(5, 'Emma Klein', '+12025550104'),
(6, 'Ali Rahimi', '+12025550105'),
(7, 'Laura Schneider', '+12025550106'),
(8, 'Amir Hosseini', '+12025550107'),
(9, 'Sofia Braun', '+12025550108'),
(10, 'Jonas Richter', '+12025550109'),
(11, 'Mia Hoffmann', '+12025550110'),
(12, 'Daniel Wagner', '+12025550111'),
(13, 'Lina Neumann', '+12025550112'),
(14, 'Noah Koch', '+12025550113'),
(15, 'Elena Berger', '+12025550114'),
(16, 'Paul Krüger', '+12025550115'),
(17, 'Olivia Schmidt', '+12025550116'),
(18, 'Felix Bauer', '+12025550117'),
(19, 'Maya Roth', '+12025550118'),
(20, 'Ben Hartmann', '+12025550119');

INSERT INTO CLASSinfo (id, name, teacher) VALUES
(1, 'Databases', 1),
(2, 'Algorithms', 2),
(3, 'Introduction to Programming', 2),
(4, 'Statistics', 3),
(5, 'Web Development', 4),
(6, 'Data Visualization', 4);

INSERT INTO ENROLLinfo (id, STDid, CLASSid) VALUES
(1, 1, 1), (2, 1, 2),
(3, 2, 1), (4, 2, 3),
(5, 3, 1),
(6, 4, 3), (7, 4, 4),
(8, 5, 2),
(9, 6, 1), (10, 6, 4),
(11, 7, 3),
(12, 8, 5),
(13, 9, 5),
(14, 10, 2), (15, 10, 4),
(16, 11, 1),
(17, 12, 5),
(18, 13, 2);

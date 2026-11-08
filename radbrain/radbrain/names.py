"""Name lists for the anonymiser (fictional use only; common names in Germany across origins).

The synthetic test generator (radbrain.synth) deliberately draws half of its planted names from a HELD-OUT list that
is NOT in here, so the 100 % recall test measures the context rules and the fail-closed check, not list lookup.
"""
from __future__ import annotations

FIRST_NAMES = set("""
Alexander Andreas Anna Anton Benjamin Bernd Birgit Brigitte Christian Christina Christine Claudia Daniel Daniela David
Dennis Dieter Dirk Doris Elena Elisabeth Emil Emily Emma Erika Ernst Eva Fabian Felix Florian Frank Franz Friedrich
Gabriele Georg Gerhard Gisela Hans Hannah Harald Heike Heinz Helga Helmut Herbert Hildegard Horst Ingrid Jan Jana Jens
Johann Johanna Jonas Jörg Josef Julia Julian Jürgen Karin Karl Katharina Kathrin Klaus Kurt Lara Laura Lea Lena Leon
Lukas Luis Lisa Manfred Manuela Marco Maria Marie Mario Markus Martin Martina Matthias Max Maximilian Melanie Michael
Michaela Mia Monika Nadine Nicole Niklas Noah Olaf Oliver Patrick Paul Peter Petra Philipp Rainer Ralf Renate Robert
Roland Rolf Rosemarie Ruth Sabine Sandra Sarah Sebastian Silke Simon Sofia Sophie Stefan Stefanie Steffen Susanne
Sven Thomas Tim Tobias Torsten Udo Ulrich Ursula Ute Uwe Walter Werner Wolfgang Yvonne
Ahmet Ali Ayşe Ayse Elif Emre Fatma Hasan Hatice Hüseyin Ibrahim İbrahim Mehmet Merve Murat Mustafa Ömer Zeynep Yusuf
Emine Leyla Can Deniz Kemal Selin Burak Cem Esra
Giuseppe Giovanni Antonio Francesco Luca Marco Alessandro Giulia Chiara Sofia Rosa Salvatore Vincenzo Angela
Piotr Paweł Pawel Krzysztof Tomasz Agnieszka Katarzyna Małgorzata Malgorzata Joanna Magdalena Andrzej
Dimitrios Georgios Konstantinos Nikolaos Ioannis Eleni Maria Sofia Vasilios
Ivan Dmitri Sergei Sergej Olga Natalia Natalja Tatjana Irina Svetlana Swetlana Alexej Wladimir Viktor Jelena
Mohammed Mohamed Muhammad Ahmad Ahmed Omar Fatima Aisha Khaled Hassan Hussein Youssef Mahmoud Amir Rania Samir
Ana Ivana Marija Milan Goran Dragan Zoran Nikola Stjepan Josip
Ajit Rajesh Priya Anil Sunil Suresh Deepa Anjali Thomas Joseph Jose John Mary
""".split())

SURNAMES = set("""
Müller Mueller Schmidt Schmitt Schneider Fischer Weber Meyer Meier Mayer Maier Wagner Becker Schulz Schulze Hoffmann
Hofmann Schäfer Schaefer Koch Bauer Richter Klein Wolf Schröder Schroeder Neumann Schwarz Zimmermann Braun Krüger
Krueger Hofmann Hartmann Lange Schmitz Werner Schmid Krause Meier Lehmann Schmid Köhler Koehler Herrmann König Koenig
Walter Mayer Huber Kaiser Fuchs Peters Lang Scholz Möller Moeller Weiß Weiss Jung Hahn Schubert Vogel Friedrich Keller
Günther Guenther Frank Berger Winkler Roth Beck Lorenz Baumann Franke Albrecht Schuster Simon Ludwig Böhm Boehm Winter
Kraus Martin Schumacher Krämer Kraemer Vogt Stein Jäger Jaeger Otto Sommer Groß Gross Seidel Heinrich Brandt Haas
Schreiber Graf Schulte Dietrich Ziegler Kuhn Kühn Pohl Engel Horn Busch Bergmann Thomas Voigt Sauer Arnold Wolff
Pfeiffer Ernst Lindner Hübner Huebner Kramer Franz Lux Wenzel Kühne Fiedler Ott Brenner Rieger Mack Bühler Buehler
Kaufmann Seifert Hermann Hauser Vollmer Haug Bader Frey Ruf Eberle Rapp Kern Spieth Häußler Rau Kurz Schäffer Mohr
Yılmaz Yilmaz Kaya Demir Şahin Sahin Çelik Celik Yıldız Yildiz Yıldırım Yildirim Öztürk Ozturk Aydın Aydin Özdemir
Ozdemir Arslan Doğan Dogan Kılıç Kilic Aslan Çetin Cetin Kara Koç Koc Kurt Özkan Ozkan Şimşek Simsek Polat Korkmaz
Rossi Russo Ferrari Esposito Bianchi Romano Colombo Ricci Marino Greco Bruno Gallo Conti De Luca Costa Giordano
Mancini Rizzo Lombardi Moretti
Nowak Kowalski Kowalska Wiśniewski Wisniewski Wójcik Wojcik Kowalczyk Kamiński Kaminski Lewandowski Zieliński
Zielinski Szymański Szymanski Woźniak Wozniak Dąbrowski Dabrowski Kozłowski Kozlowski Jankowski Mazur
Papadopoulos Papadopoulou Georgiou Nikolaou Pappas Ioannou Dimitriou Konstantinou
Ivanov Iwanow Petrov Petrow Smirnov Smirnow Popov Popow Volkov Wolkow Kuznetsov Kusnezow Sokolov Morozov Lebedev
Novak Horvat Kovačević Kovacevic Babić Babic Marić Maric Jurić Juric Knežević Knezevic Petrović Petrovic Jovanović
Jovanovic Nikolić Nikolic
Al-Hassan Hassan Ahmadi Hosseini Mohammadi Rahimi Karimi Haddad Khalil Saleh Mansour Nasser Ibrahim Abdullah
Nguyen Tran Pham Le Hoang Kumar Singh Sharma Patel Gupta Nair Menon Pillai Jose Joseph Varghese Mathew Thomas
""".split())

# Words that are on the lists above but are also everyday/medical words: never scrubbed on their own, only in a
# name context (Herr/Frau/Dr./mitgeteilt an ...).
AMBIGUOUS = {"Klein", "Lang", "Groß", "Gross", "Jung", "Kurz", "Frank", "Ernst", "Winter", "Sommer", "Stein", "Horn",
             "Engel", "Graf", "Kern", "Weiß", "Weiss", "Schwarz", "Braun", "Wolf", "Fuchs", "Vogel", "Hahn", "Koch",
             "Bauer", "Kaiser", "König", "Koenig", "Richter", "Fischer", "Weber", "Becker", "Simon", "Martin",
             "Thomas", "Otto", "Bruno", "Costa", "Mohr", "Rau", "Ruf", "Mack", "Lux", "Pohl", "Arnold", "Hermann",
             "Franz", "Ludwig", "Albrecht", "Walter", "Werner", "Peters", "Le", "Kara", "Kurt", "Hoffa", "Maria",
             "Lea", "Max", "Paul", "Emil", "Luca", "Can", "Deniz", "Rosa", "Ana", "Eva", "Ali", "John", "Mary",
             "Jose", "Joseph", "Johann", "Georg", "Karl", "Hans", "Peter", "Petra", "Nikola", "Ibrahim", "Hassan",
             "Heinrich", "Friedrich", "Lorenz", "Sauer", "Voigt", "Busch", "Kraus", "Beck", "Roth", "Haas", "Frey",
             "Sahin", "Kaya", "Demir", "Polat", "Singh", "Kumar", "Patel", "Nair", "Menon", "Pillai"}

# Eponyms and classifications that look like surnames but are medical text (must survive anonymisation).
EPONYMS = set("""
Crohn Bankart Hill Sachs Hill-Sachs Monteggia Galeazzi Colles Smith Barton Weber Bechterew Baker Hoffa Schmorl
Scheuermann Perthes Osgood Schlatter Osgood-Schlatter Sudeck Chilaiditi Kerley Fleischner Virchow Bosniak Tossy
Rockwood Garden Pipkin Neer Frykman Salter Harris Salter-Harris Gustilo Schatzker Hawkins Lisfranc Chopart Jones
Maisonneuve Pauwels Denis Magerl Meyerding Modic Pfirrmann Outerbridge Segond Stener Bennett Rolando Kienböck
Kienboeck Preiser Madelung Hangman Jefferson Chance Klippel Feil Arnold Chiari Arnold-Chiari Dandy Walker Wernicke
Binswanger Fahr Moyamoya Stanford DeBakey Leriche Fontaine Rutherford Budd Budd-Chiari Caroli Mirizzi Klatskin
Courvoisier Meckel Hirschsprung Wilms Ewing Paget Hodgkin Kaposi Pancoast Hampton Westermark Golden Bochdalek
Morgagni Zenker Barrett Boerhaave Mallory Weiss Mallory-Weiss Gerota Douglas Morison Glisson Riedel Couinaud Willis
Galen Monro Sylvius Luschka Magendie Baastrup Forestier Romanus Andersson Tietze Poland Cushing Conn Addison Graves
Basedow Hashimoto Gleason Fazekas Spetzler Hunt Hess Fisher Glasgow Seldinger Judkins Simmons Cobra Valsalva
Trendelenburg Lauenstein Rippstein Dunn Faux-Profil Merchant Frik Rosenberg Kellgren Lawrence Kellgren-Lawrence
Ficat Steinberg Mitchell Tönnis Toennis Wiberg Sharp Kohler Köhler Freiberg Sever Haglund Morton Bristow Latarjet
Bankart-Läsion Hill-Sachs-Delle Codman Bigliani Patte Goutallier Thomas Ranawat Insall Salvati Caton Deschamps Wiberg
Wrisberg Humphry Hoffa-Fettkörper Baker-Zyste Stieda Pellegrini Pellegrini-Stieda Cyclops Ahlbäck Ahlback Blount
Legg Calvé Calve Legg-Calvé-Perthes Mayo Kocher Lauge Hansen Lauge-Hansen Danis Danis-Weber Tillaux Thurston
Holland Thurston-Holland Essex Lopresti Essex-Lopresti Herbert Russe Mayfield Lichtman Gilula Terry Thomas
Sinding Larsen Sinding-Larsen Johansson Hoffmann Babinski Horner Brown Séquard Sequard Guillain Barré Barre Bell
Cobb Risser Ferguson Wiltse Taillard Spurling Lhermitte Tarlov Lindau Hippel Recklinghausen Bourneville Sturge
Weber-Sturge Sturge-Weber Rendu Osler Rendu-Osler Peutz Jeghers Gardner Lynch Menetrier Ménétrier Whipple
Zollinger Ellison Morbus Wegener Churg Strauss Takayasu Kawasaki Raynaud Buerger Löffler Loeffler Hamman Rich
Swyer James MacLeod Kartagener Mounier Kuhn Lady Windermere Ghon Ranke Simon Assmann Pott Kümmell Kuemmell
Baastrup Forestier Lewis Bertin Randall Brödel Brodel Ormond Fournier Peyronie Morgagni Hydatide Gartner Nabothi
Bartholin Krukenberg Meigs Brenner Sertoli Leydig Skene Cowper Douglas Retzius Hesselbach Spieghel Spigelius Petit
Grynfeltt Amyand Littre Richter Maydl Garengeot Treitz Bauhin Kerckring Oddi Vater Santorini Wirsung Calot
Hartmann Rokitansky Aschoff Luschka Couinaud Glisson Cantlie Rex Arantius Spiegel Riedel Tait Murphy McBurney
Lanz Rovsing Blumberg Psoas Cullen Grey Turner Kehr Charcot Reynolds Mirizzi Bouveret Rigler Chilaiditi
""".split())

TITLES = r"(?:Prof\.?|Professor(?:in)?|PD|Priv\.-?Doz\.?|Dr\.?|Dres\.?|med\.?|habil\.?|dent\.?|rer\.?\s?nat\.?|univ\.?|" \
         r"Dipl\.-?Med\.?|M\.?D\.?|FA|FÄ|OA|OÄ|CA|CÄ|LOA|LOÄ|AA|AÄ|Oberarzt|Oberärztin|Chefarzt|Chefärztin|" \
         r"Assistenzarzt|Assistenzärztin|Facharzt|Fachärztin|Kollegen|Kollege|Kollegin|Hausarzt|Hausärztin|Herrn|Herr|Frau|Hrn\.?|Hr\.?|" \
         r"Fr\.?|Pat\.?|Patient|Patientin|Pfleger|Schwester|MTRA|MTR|MFA)"

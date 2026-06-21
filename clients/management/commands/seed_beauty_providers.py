"""
Seed 12+ realistic beauty providers in Montreal, Laval, and Brossard.
Run: python manage.py seed_beauty_providers
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from clients.models import BeautyProvider, BeautyService, ProviderReview, StaffMember, OpeningHours
from datetime import time


PROVIDERS = [
    # ═══ Medical Aesthetics (4) ═══
    {
        "name": "Clinique Diva",
        "category": "medical_aesthetics",
        "description": "Montreal's premier medical aesthetics clinic offering advanced Botox, dermal fillers, and laser treatments. Our board-certified physicians combine artistry with the latest technology to deliver natural, stunning results in a luxurious setting.",
        "address": "1245 Rue Sherbrooke Ouest",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H3G 1G2",
        "latitude": 45.4989,
        "longitude": -73.5777,
        "phone": "(514) 555-0147",
        "website": "https://cliniquediva.com",
        "email": "info@cliniquediva.com",
        "instagram": "https://instagram.com/cliniquediva",
        "tiktok": "https://tiktok.com/@cliniquediva",
        "facebook": "https://facebook.com/cliniquediva",
        "whatsapp": "15145550147",
        "rating": 4.8,
        "review_count": 134,
        "is_featured": True,
        "opening_hours": [
            (0, time(9,0), time(18,0), False),
            (1, time(9,0), time(18,0), False),
            (2, time(9,0), time(18,0), False),
            (3, time(9,0), time(20,0), False),
            (4, time(9,0), time(17,0), False),
            (5, time(10,0), time(16,0), False),
            (6, None, None, True),
        ],
        "staff": [
            ("Dr. Sophie Tremblay", "Medical Director & Lead Injector", "Board-certified physician with 15+ years in aesthetic medicine. Trained in Paris and New York."),
            ("Marie-Claude Bérubé", "Senior Aesthetic Nurse", "Specialist in dermal fillers and PRP treatments with an artist's eye for facial harmony."),
            ("Julien Lefebvre", "Laser Specialist", "Certified laser safety officer with expertise in all skin types and the latest diode technology."),
        ],
        "services": [
            ("Botox — Forehead & Crow's Feet", 380, 30, True),
            ("Dermal Fillers — Lips", 550, 45, True),
            ("Dermal Fillers — Cheeks", 650, 45, False),
            ("Laser Skin Rejuvenation", 420, 60, False),
            ("PRP Facial (Vampire Facial)", 750, 60, False),
        ],
        "reviews": [
            ("Marie L.", 5, "Absolutely stunning results. Dr. Tremblay is an artist. The clinic is beautiful and the staff made me feel so comfortable. Will be coming back for sure."),
            ("Sophie D.", 5, "Best Botox in Montreal. Natural results — nobody can tell I've had anything done. I just look refreshed."),
            ("Camille R.", 4, "Great experience overall. A bit pricey but you get what you pay for. The consultation was thorough and I never felt rushed."),
        ],
    },
    {
        "name": "MédiSpa Royal",
        "category": "medical_aesthetics",
        "description": "Laval's top-rated medical spa specializing in Hydrafacial, PRP therapy, microneedling, and advanced skin treatments. We combine medical expertise with a spa-like experience for results you can see and feel.",
        "address": "3030 Boul. le Carrefour",
        "city": "Laval",
        "province": "QC",
        "postal_code": "H7T 2K7",
        "latitude": 45.5580,
        "longitude": -73.7453,
        "phone": "(450) 555-0234",
        "website": "https://medisparoyal.com",
        "email": "bonjour@medisparoyal.com",
        "rating": 4.7,
        "review_count": 98,
        "is_featured": True,
        "services": [
            ("Hydrafacial Deluxe", 250, 60, True),
            ("PRP Hair Restoration", 680, 75, False),
            ("Microneedling with RF", 520, 60, True),
            ("Chemical Peel — Medium Depth", 180, 30, False),
            ("LED Light Therapy", 95, 20, False),
        ],
        "reviews": [
            ("Isabelle M.", 5, "The Hydrafacial here is incredible. My skin has never looked this good. The clinic is spotless and the staff are so knowledgeable."),
            ("Julie T.", 4, "Really great microneedling results. I've done 3 sessions and my acne scars are barely visible now. Highly recommend."),
        ],
    },
    {
        "name": "Epiderma Montreal",
        "category": "medical_aesthetics",
        "description": "Specialized laser hair removal and skin rejuvenation clinic in the heart of downtown Montreal. Using the latest diode and IPL technology for safe, effective treatments on all skin types.",
        "address": "2100 Rue de la Montagne",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H3G 1Z7",
        "latitude": 45.4970,
        "longitude": -73.5770,
        "phone": "(514) 555-0367",
        "website": "https://epidermamontreal.com",
        "email": "contact@epidermamontreal.com",
        "rating": 4.5,
        "review_count": 210,
        "is_featured": False,
        "services": [
            ("Laser Hair Removal — Full Legs", 320, 45, True),
            ("Laser Hair Removal — Underarms", 120, 15, True),
            ("Laser Hair Removal — Bikini", 180, 20, False),
            ("IPL Photofacial", 280, 30, False),
            ("Skin Tightening", 450, 60, False),
        ],
        "reviews": [
            ("Nadia B.", 5, "I've done 6 sessions for full legs and the results are amazing. Almost no regrowth after 2 years. The technicians are super professional."),
            ("Amélie G.", 4, "Good results, clean clinic. Parking downtown is a bit annoying but the treatment is worth it. Prices are fair for the quality."),
            ("Fatima K.", 5, "Finally found a place that knows how to treat darker skin tones safely. They did a patch test and everything. So happy!"),
        ],
    },
    {
        "name": "Dermabelle Brossard",
        "category": "medical_aesthetics",
        "description": "South Shore's boutique aesthetic clinic offering personalized Botox, fillers, and chemical peels in an intimate, welcoming environment. We believe in enhancing your natural beauty — not changing it.",
        "address": "8500 Boul. Taschereau",
        "city": "Brossard",
        "province": "QC",
        "postal_code": "J4X 2T4",
        "latitude": 45.4460,
        "longitude": -73.4690,
        "phone": "(450) 555-0456",
        "website": "https://dermabelle.com",
        "email": "info@dermabelle.com",
        "rating": 4.6,
        "review_count": 67,
        "is_featured": False,
        "services": [
            ("Botox — Glabella (Frown Lines)", 300, 20, True),
            ("Lip Fillers — Natural Look", 450, 40, True),
            ("Chemical Peel — Light", 140, 30, False),
            ("Skin Consultation", 75, 30, False),
            ("Microneedling", 350, 50, False),
        ],
        "reviews": [
            ("Chantal V.", 5, "Dr. Bélanger is so gentle and has such a good eye. My lips look completely natural — exactly what I asked for. The clinic is adorable."),
            ("Mélanie P.", 4, "Great spot on the South Shore. No need to drive to Montreal for quality treatments. Prices are reasonable and parking is easy."),
        ],
    },

    # ═══ Hair (4) ═══
    {
        "name": "Salon Le Cartier",
        "category": "hair",
        "description": "Upscale hair salon in Old Montreal offering expert cuts, color, balayage, and premium hair extensions. Our master stylists bring 20+ years of experience from Paris and New York to every chair.",
        "address": "445 Rue Saint-Paul Ouest",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2Y 2A6",
        "latitude": 45.5017,
        "longitude": -73.5550,
        "phone": "(514) 555-0678",
        "website": "https://salonlecartier.com",
        "email": "rdv@salonlecartier.com",
        "rating": 4.9,
        "review_count": 187,
        "is_featured": True,
        "services": [
            ("Women's Cut & Style", 95, 60, True),
            ("Balayage — Full", 320, 150, True),
            ("Single Process Color", 140, 90, False),
            ("Hair Extensions — Full Head", 850, 180, False),
            ("Keratin Treatment", 380, 120, False),
        ],
        "reviews": [
            ("Gabrielle F.", 5, "Hands down the best balayage in Montreal. Antoine is a true artist. Yes, it's expensive, but my hair has never looked this good."),
            ("Léa C.", 5, "The Old Montreal location is stunning. Worth the visit just for the ambiance. But the hair? Incredible. I've found my forever salon."),
            ("Emma R.", 4, "Beautiful salon with very talented stylists. The only downside is they book up weeks in advance. Plan ahead!"),
        ],
    },
    {
        "name": "Coiffure Moderne Laval",
        "category": "hair",
        "description": "Modern, welcoming hair salon in the heart of Laval. We specialize in contemporary cuts, vibrant color, head spa treatments, and keratin smoothing. A friendly, bilingual team ready to transform your look.",
        "address": "1555 Boul. Daniel-Johnson",
        "city": "Laval",
        "province": "QC",
        "postal_code": "H7V 1E6",
        "latitude": 45.5600,
        "longitude": -73.7300,
        "phone": "(450) 555-0789",
        "website": "https://coiffuremodernelaval.com",
        "email": "info@coiffuremodernelaval.com",
        "instagram": "https://instagram.com/coiffuremodernelaval",
        "tiktok": "",
        "facebook": "https://facebook.com/coiffuremodernelaval",
        "whatsapp": "14505550234",
        "rating": 4.5,
        "review_count": 112,
        "is_featured": False,
        "opening_hours": [
            (0, None, None, True),
            (1, time(9,0), time(19,0), False),
            (2, time(9,0), time(19,0), False),
            (3, time(9,0), time(21,0), False),
            (4, time(9,0), time(19,0), False),
            (5, time(8,0), time(17,0), False),
            (6, time(10,0), time(15,0), False),
        ],
        "staff": [
            ("Mélanie Dubois", "Master Stylist & Owner", "20 years of experience. Specializes in balayage, precision cuts, and bridal styling. Trained at L'Oréal Academy Paris."),
            ("Alexandre Côté", "Senior Colorist", "Bayalage and lived-in color expert. Known for creating the perfect 'French girl' blonde."),
            ("Camille Nguyen", "Head Spa Specialist", "Certified in Japanese head spa techniques. Brings a holistic approach to scalp health and hair wellness."),
        ],
        "services": [
            ("Women's Cut & Blow-dry", 75, 60, True),
            ("Head Spa Treatment", 120, 45, True),
            ("Full Highlights", 220, 120, False),
            ("Brazilian Keratin Smoothing", 350, 150, False),
            ("Men's Cut", 45, 30, False),
        ],
        "reviews": [
            ("Karine L.", 5, "The head spa is a dream. I came in exhausted and left feeling like a new person. My hair looks amazing too. Great value."),
            ("David M.", 4, "Best men's cut in Laval. Actually takes time to understand what you want. The hot towel finish is a nice touch."),
        ],
    },
    {
        "name": "Luxe Extensions Montréal",
        "category": "hair",
        "description": "Montreal's extension specialists. We offer hand-tied, tape-in, and keratin bond extensions using only ethically sourced, premium Remy hair. Custom color-matching ensures seamless, natural-looking results every time.",
        "address": "1020 Rue Laurier Ouest",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2V 2K8",
        "latitude": 45.5236,
        "longitude": -73.5965,
        "phone": "(514) 555-0890",
        "website": "https://luxeextensionsmtl.com",
        "email": "hello@luxeextensionsmtl.com",
        "rating": 4.8,
        "review_count": 54,
        "is_featured": True,
        "services": [
            ("Consultation & Color Match", 50, 30, False),
            ("Hand-Tied Extensions — Full", 950, 180, True),
            ("Tape-In Extensions — Full", 650, 120, True),
            ("Extension Maintenance", 150, 60, False),
            ("Extension Removal", 100, 45, False),
        ],
        "reviews": [
            ("Vanessa S.", 5, "My extensions are completely undetectable. Sarah matched my color perfectly. I have fine hair and these give me so much volume. Life-changing!"),
            ("Audrey M.", 5, "Worth every penny. The quality of the hair is exceptional — I've had mine for 8 months and they still look great. Amazing service."),
        ],
    },
    {
        "name": "Studio K Beauté",
        "category": "hair",
        "description": "Chic Brossard salon offering precision cuts, luxurious styling, and the best blowouts on the South Shore. Our friendly, talented team creates looks that make you feel confident and beautiful — for any occasion.",
        "address": "6800 Boul. Taschereau",
        "city": "Brossard",
        "province": "QC",
        "postal_code": "J4W 1M8",
        "latitude": 45.4600,
        "longitude": -73.4650,
        "phone": "(450) 555-0901",
        "website": "https://studiokbeaute.com",
        "email": "coucou@studiokbeaute.com",
        "rating": 4.4,
        "review_count": 73,
        "is_featured": False,
        "services": [
            ("Signature Blowout", 55, 45, True),
            ("Women's Cut & Style", 70, 60, False),
            ("Event Styling", 120, 90, True),
            ("Balayage — Partial", 240, 120, False),
            ("Olaplex Treatment", 65, 30, False),
        ],
        "reviews": [
            ("Annie D.", 5, "Got my wedding hair done here and it was perfect. Stayed all night. The team is so sweet and talented. Best blowout bar on the South Shore!"),
            ("Jessica T.", 4, "Really cute salon, great vibes. Prices are fair and the stylists actually listen. My balayage turned out exactly like the reference photo."),
        ],
    },

    # ═══ Beauty (4) ═══
    {
        "name": "Ongles Prestige",
        "category": "beauty",
        "description": "Montreal's luxury nail studio in the Plateau. Specializing in Russian manicures, gel extensions, and intricate nail art. A serene, Instagram-worthy space where every detail is designed for your comfort.",
        "address": "3950 Rue Saint-Denis",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2W 2M2",
        "latitude": 45.5189,
        "longitude": -73.5753,
        "phone": "(514) 555-1011",
        "website": "https://onglesprestige.com",
        "email": "info@onglesprestige.com",
        "rating": 4.7,
        "review_count": 156,
        "is_featured": True,
        "services": [
            ("Russian Manicure", 85, 75, True),
            ("Gel Extension — Full Set", 120, 90, True),
            ("Nail Art — Per Nail", 15, 10, False),
            ("Spa Pedicure", 95, 60, False),
            ("Gel Polish Change", 55, 30, False),
        ],
        "reviews": [
            ("Clara M.", 5, "The cleanest, most beautiful nail salon I've ever been to. My Russian manicure lasted 3 weeks with zero chips. The attention to detail is unmatched."),
            ("Mia K.", 5, "I'm obsessed. The nail art here is next level — they can recreate anything you show them. It's pricey but you're paying for quality."),
            ("Rosalie G.", 4, "Beautiful salon, great service. The only reason it's not 5 stars is because they're always running a bit behind schedule. But worth the wait!"),
        ],
    },
    {
        "name": "Lash & Brow Atelier",
        "category": "beauty",
        "description": "Dedicated lash and brow studio in Laval. We specialize in classic and volume eyelash extensions, lash lifts, microblading, brow lamination, and brow shaping. Every treatment is customized to your unique features.",
        "address": "2155 Boul. Saint-Martin Ouest",
        "city": "Laval",
        "province": "QC",
        "postal_code": "H7S 1M9",
        "latitude": 45.5700,
        "longitude": -73.7200,
        "phone": "(450) 555-1122",
        "website": "https://lashbrowatelier.com",
        "email": "hello@lashbrowatelier.com",
        "rating": 4.6,
        "review_count": 89,
        "is_featured": False,
        "services": [
            ("Classic Lash Extensions — Full Set", 150, 120, True),
            ("Volume Lash Extensions — Full Set", 190, 150, True),
            ("Lash Lift & Tint", 95, 60, False),
            ("Microblading — Initial Session", 450, 150, False),
            ("Brow Lamination", 85, 45, False),
        ],
        "reviews": [
            ("Naomi B.", 5, "My lashes are perfect. I've been getting them done here for 6 months and they always look amazing. The studio is so clean and relaxing."),
            ("Sarah L.", 4, "Really talented brow artist. My microblading healed beautifully. A bit of a wait for the initial appointment but totally worth it."),
        ],
    },
    {
        "name": "Beauté Pure",
        "category": "beauty",
        "description": "Montreal's go-to destination for professional makeup artistry, brow sculpting, lash extensions, and spray tanning. Our artists work on fashion week, film sets, and bridal parties — bringing editorial expertise to every client.",
        "address": "1227 Rue de la Montagne",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H3G 1Z2",
        "latitude": 45.4960,
        "longitude": -73.5750,
        "phone": "(514) 555-1313",
        "website": "https://beautepuremtl.com",
        "email": "info@beautepuremtl.com",
        "rating": 4.5,
        "review_count": 71,
        "is_featured": False,
        "services": [
            ("Bridal Makeup", 250, 90, True),
            ("Event Makeup", 150, 60, True),
            ("Brow Sculpting & Tint", 65, 30, False),
            ("Classic Lash Extensions", 140, 110, False),
            ("Spray Tan", 60, 20, False),
        ],
        "reviews": [
            ("Émilie R.", 5, "Did my wedding makeup and it was flawless. Lasted 14 hours through tears, dancing, and humidity. I've never felt more beautiful."),
            ("Léonie T.", 4, "Great makeup artists who really know how to work with different skin tones. My only wish is they had more weekend availability."),
        ],
    },
    {
        "name": "Studio Magnifique",
        "category": "beauty",
        "description": "Full-service beauty studio in Laval offering premium nails, lashes, makeup, and waxing services. Our warm, welcoming space is designed to be your beauty sanctuary — come in, relax, and leave feeling magnificent.",
        "address": "800 Rue de la Concorde",
        "city": "Laval",
        "province": "QC",
        "postal_code": "H7G 2H7",
        "latitude": 45.5750,
        "longitude": -73.6900,
        "phone": "(450) 555-1414",
        "website": "https://studiomagnifique.com",
        "email": "bonjour@studiomagnifique.com",
        "rating": 4.4,
        "review_count": 48,
        "is_featured": False,
        "services": [
            ("Gel Manicure", 65, 45, True),
            ("Hybrid Lash Extensions", 160, 120, True),
            ("Makeup Application", 110, 60, False),
            ("Deluxe Spa Pedicure", 85, 60, False),
            ("Full Face Waxing", 55, 30, False),
        ],
        "reviews": [
            ("Catherine D.", 5, "Such a hidden gem in Laval! I get my nails and lashes done here and always leave feeling amazing. The staff is so friendly and talented."),
            ("Laura M.", 4, "Really nice studio with great vibes. My gel manicure lasted almost 3 weeks. The only thing is parking can be tricky."),
        ],
    },

    # ═══ Brossard Nail & Lash Studio ═══
    {
        "name": "Ongles & Cils Brossard",
        "category": "beauty",
        "description": "South Shore's most-loved nail and lash destination. We specialize in premium gel extensions, stunning nail art, Russian manicures, and volume eyelash extensions. Our bright, modern studio on Taschereau is designed to be your weekly beauty escape — come for the nails, stay for the vibe.",
        "address": "7800 Boul. Taschereau",
        "city": "Brossard",
        "province": "QC",
        "postal_code": "J4X 1C2",
        "latitude": 45.4480,
        "longitude": -73.4700,
        "phone": "(450) 555-2020",
        "website": "https://onglescilsbrossard.com",
        "email": "bonjour@onglescilsbrossard.com",
        "instagram": "https://instagram.com/onglescilsbrossard",
        "tiktok": "https://tiktok.com/@onglescilsbrossard",
        "facebook": "https://facebook.com/onglescilsbrossard",
        "whatsapp": "14505552020",
        "rating": 4.7,
        "review_count": 91,
        "is_featured": True,
        "opening_hours": [
            (0, None, None, True),
            (1, time(10,0), time(19,0), False),
            (2, time(10,0), time(19,0), False),
            (3, time(10,0), time(20,0), False),
            (4, time(10,0), time(19,0), False),
            (5, time(9,0), time(17,0), False),
            (6, time(10,0), time(16,0), False),
        ],
        "staff": [
            ("Jessica Tran", "Owner & Senior Nail Artist", "Award-winning nail artist with 10 years of experience. Specializes in intricate hand-painted designs and Russian manicures."),
            ("Vanessa Pham", "Lash Artist", "Certified in volume, hybrid, and mega-volume techniques. Known for creating custom lash maps that perfectly suit each client's eye shape."),
            ("Amina Bensalem", "Nail Artist & Brow Specialist", "Dual specialist in nail art and brow lamination. Brings a meticulous eye for symmetry to every service."),
        ],
        "services": [
            ("Russian Manicure", 80, 75, True),
            ("Gel Extension — Full Set", 110, 90, True),
            ("Volume Lash Extensions — Full Set", 175, 140, True),
            ("Nail Art — Per Nail", 12, 10, False),
            ("Brow Lamination", 80, 45, False),
            ("Spa Pedicure", 75, 55, False),
        ],
        "reviews": [
            ("Sarah M.", 5, "My absolute favorite nail studio on the South Shore! Jessica is a true artist — my nail art always gets compliments. The studio is so clean and pretty."),
            ("Lina Z.", 5, "Best lash extensions I've ever had. Vanessa took the time to understand exactly what I wanted. They've lasted 3 weeks and still look amazing."),
            ("Dominique R.", 4, "Great atmosphere and talented artists. Prices are fair for the quality. Only wish they had more evening slots — they book up fast!"),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed 12 realistic beauty providers in Montreal, Laval, and Brossard'

    def handle(self, *args, **options):
        created = 0
        for data in PROVIDERS:
            services_data = data.pop("services")
            reviews_data = data.pop("reviews")
            hours_data = data.pop("opening_hours", [])
            staff_data = data.pop("staff", [])

            provider, is_new = BeautyProvider.objects.get_or_create(
                slug=slugify(data["name"]),
                defaults=data,
            )
            if not is_new:
                # Update existing provider data
                for key, value in data.items():
                    setattr(provider, key, value)
                provider.save()

            # Clear and recreate services
            provider.services.all().delete()
            for svc in services_data:
                BeautyService.objects.create(
                    provider=provider,
                    name=svc[0],
                    price=svc[1],
                    duration_minutes=svc[2],
                    is_popular=svc[3],
                )

            # Clear and recreate opening hours
            provider.opening_hours.all().delete()
            for h in hours_data:
                OpeningHours.objects.create(
                    provider=provider,
                    day=h[0],
                    open_time=h[1],
                    close_time=h[2],
                    is_closed=h[3],
                )

            # Add staff if none exist
            if not provider.staff.exists():
                for i, s in enumerate(staff_data):
                    StaffMember.objects.create(
                        provider=provider,
                        name=s[0],
                        role=s[1],
                        bio=s[2],
                        order=i,
                    )

            # Add reviews if none exist
            if not provider.reviews.exists():
                for rev in reviews_data:
                    ProviderReview.objects.create(
                        provider=provider,
                        author_name=rev[0],
                        rating=rev[1],
                        body=rev[2],
                        is_verified=True,
                    )

            if is_new:
                created += 1
            self.stdout.write(
                self.style.SUCCESS(f'  [OK] {provider.name} ({provider.get_category_display()}) - {provider.services.count()} services, {provider.reviews.count()} reviews')
            )

        total = BeautyProvider.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\nDone! {created} new providers created. {total} total providers in database.'))

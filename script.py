import pandas as pd

# Lista completa con 50 registros de muestra
data = [
    # --- CALZADO (10 registros) ---
    {"codigo": "NIKE-R1-32", "nombre": "Nike R1 Negro Rojo", "categoria": "Calzado", "marca": "Nike", "referencia": "R1", "color": "Negro/Rojo", "talla": "32", "precio_costo": 90000, "precio": 160000, "stock": 10},
    {"codigo": "NIKE-AF1-38", "nombre": "Nike Air Force 1 Blancas", "categoria": "Calzado", "marca": "Nike", "referencia": "AF1", "color": "Blanco", "talla": "38", "precio_costo": 110000, "precio": 210000, "stock": 8},
    {"codigo": "ADID-FOR-39", "nombre": "Adidas Forum Low", "categoria": "Calzado", "marca": "Adidas", "referencia": "Forum", "color": "Blanco/Azul", "talla": "39", "precio_costo": 105000, "precio": 195000, "stock": 6},
    {"codigo": "PUMA-RSX-40", "nombre": "Puma RS-X Reinvention", "categoria": "Calzado", "marca": "Puma", "referencia": "RS-X", "color": "Multicolor", "talla": "40", "precio_costo": 95000, "precio": 180000, "stock": 4},
    {"codigo": "NEW-550-37", "nombre": "New Balance 550", "categoria": "Calzado", "marca": "New Balance", "referencia": "550", "color": "Blanco/Verde", "talla": "37", "precio_costo": 120000, "precio": 230000, "stock": 5},
    {"codigo": "VANS-OLD-41", "nombre": "Vans Old Skool Classic", "categoria": "Calzado", "marca": "Vans", "referencia": "Old Skool", "color": "Negro/Blanco", "talla": "41", "precio_costo": 75000, "precio": 140000, "stock": 12},
    {"codigo": "CONV-ALL-36", "nombre": "Converse Chuck Taylor Bota", "categoria": "Calzado", "marca": "Converse", "referencia": "Chuck 70", "color": "Negro", "talla": "36", "precio_costo": 70000, "precio": 135000, "stock": 9},
    {"codigo": "JORD-1-42", "nombre": "Air Jordan 1 Retro High", "categoria": "Calzado", "marca": "Jordan", "referencia": "AJ1", "color": "Rojo/Negro", "talla": "42", "precio_costo": 140000, "precio": 280000, "stock": 3},
    {"codigo": "REEB-CL-38", "nombre": "Reebok Club C 85", "categoria": "Calzado", "marca": "Reebok", "referencia": "Club C", "color": "Blanco", "talla": "38", "precio_costo": 80000, "precio": 150000, "stock": 7},
    {"codigo": "FILA-DIS-39", "nombre": "Fila Disruptor II", "categoria": "Calzado", "marca": "Fila", "referencia": "Disruptor", "color": "Blanco", "talla": "39", "precio_costo": 85000, "precio": 165000, "stock": 5},

    # --- ROPA (20 registros) ---
    {"codigo": "ZARA-CAM-M", "nombre": "Camisa Oversize Básica", "categoria": "Ropa", "marca": "Zara", "referencia": "Basic", "color": "Blanco", "talla": "M", "precio_costo": 45000, "precio": 85000, "stock": 15},
    {"codigo": "ZARA-CAM-L", "nombre": "Camisa Oversize Básica", "categoria": "Ropa", "marca": "Zara", "referencia": "Basic", "color": "Negro", "talla": "L", "precio_costo": 45000, "precio": 85000, "stock": 14},
    {"codigo": "LEVI-JEA-32", "nombre": "Jeans Slim Fit 511", "categoria": "Ropa", "marca": "Levi's", "referencia": "511", "color": "Azul Oscuro", "talla": "32", "precio_costo": 70000, "precio": 145000, "stock": 10},
    {"codigo": "LEVI-JEA-30", "nombre": "Jeans Straight 501", "categoria": "Ropa", "marca": "Levi's", "referencia": "501", "color": "Azul Claro", "talla": "30", "precio_costo": 75000, "precio": 155000, "stock": 8},
    {"codigo": "HM-HOO-M", "nombre": "Hoodie Minimalista con Capucha", "categoria": "Ropa", "marca": "H&M", "referencia": "HoodieBasic", "color": "Gris", "talla": "M", "precio_costo": 50000, "precio": 95000, "stock": 11},
    {"codigo": "HM-HOO-S", "nombre": "Hoodie Minimalista con Capucha", "categoria": "Ropa", "marca": "H&M", "referencia": "HoodieBasic", "color": "Negro", "talla": "S", "precio_costo": 50000, "precio": 95000, "stock": 7},
    {"codigo": "STRAD-POL-M", "nombre": "Polo Classic Fit", "categoria": "Ropa", "marca": "Stradivarius", "referencia": "PoloC", "color": "Azul Navy", "talla": "M", "precio_costo": 35000, "precio": 70000, "stock": 13},
    {"codigo": "STRAD-POL-L", "nombre": "Polo Classic Fit", "categoria": "Ropa", "marca": "Stradivarius", "referencia": "PoloC", "color": "Blanco", "talla": "L", "precio_costo": 35000, "precio": 70000, "stock": 9},
    {"codigo": "PULL-JOG-M", "nombre": "Jogger Casual Urbano", "categoria": "Ropa", "marca": "Pull&Bear", "referencia": "JoggerUrb", "color": "Negro", "talla": "M", "precio_costo": 48000, "precio": 90000, "stock": 10},
    {"codigo": "PULL-JOG-L", "nombre": "Jogger Casual Urbano", "categoria": "Ropa", "marca": "Pull&Bear", "referencia": "JoggerUrb", "color": "Gris Oscuro", "talla": "L", "precio_costo": 48000, "precio": 90000, "stock": 6},
    {"codigo": "BERS-CHA-M", "nombre": "Chaqueta Cortavientos", "categoria": "Ropa", "marca": "Bershka", "referencia": "WindV", "color": "Negro/Verde", "talla": "M", "precio_costo": 65000, "precio": 130000, "stock": 5},
    {"codigo": "BERS-CHA-L", "nombre": "Chaqueta Cortavientos", "categoria": "Ropa", "marca": "Bershka", "referencia": "WindV", "color": "Negro/Rojo", "talla": "L", "precio_costo": 65000, "precio": 130000, "stock": 4},
    {"codigo": "NIKE-SHO-M", "nombre": "Short Deportivo Dry-Fit", "categoria": "Ropa", "marca": "Nike", "referencia": "DryFit", "color": "Negro", "talla": "M", "precio_costo": 30000, "precio": 65000, "stock": 15},
    {"codigo": "ADID-SHO-L", "nombre": "Short Deportivo Essentials", "categoria": "Ropa", "marca": "Adidas", "referencia": "EssShort", "color": "Gris", "talla": "L", "precio_costo": 32000, "precio": 68000, "stock": 12},
    {"codigo": "CALV-BOX-M", "nombre": "Bóxer Pack x3 Modern Cotton", "categoria": "Ropa", "marca": "Calvin Klein", "referencia": "Boxer3x", "color": "Multicolor", "talla": "M", "precio_costo": 40000, "precio": 80000, "stock": 20},
    {"codigo": "CALV-BOX-L", "nombre": "Bóxer Pack x3 Modern Cotton", "categoria": "Ropa", "marca": "Calvin Klein", "referencia": "Boxer3x", "color": "Negro", "talla": "L", "precio_costo": 40000, "precio": 80000, "stock": 18},
    {"codigo": "TOMM-RET-M", "nombre": "Camiseta Estampada Retro", "categoria": "Ropa", "marca": "Tommy Hilfiger", "referencia": "RetroTee", "color": "Blanco", "talla": "M", "precio_costo": 45000, "precio": 95000, "stock": 10},
    {"codigo": "LACO-POL-M", "nombre": "Polo Classic Piqué", "categoria": "Ropa", "marca": "Lacoste", "referencia": "PiqueClassic", "color": "Verde", "talla": "M", "precio_costo": 70000, "precio": 145000, "stock": 6},
    {"codigo": "THEN-M", "nombre": "Chaqueta Impermeable", "categoria": "Ropa", "marca": "The North Face", "referencia": "ApexB", "color": "Negro", "talla": "M", "precio_costo": 120000, "precio": 240000, "stock": 3},
    {"codigo": "CARH-SWE-L", "nombre": "Sweater Regular Fit", "categoria": "Ropa", "marca": "Carhartt", "referencia": "Workwear", "color": "Marrón", "talla": "L", "precio_costo": 80000, "precio": 160000, "stock": 5},

    # --- FRAGANCIAS (10 registros) ---
    {"codigo": "HUGO-BOSS-1", "nombre": "Perfume Boss Bottled 100ml", "categoria": "Fragancias", "marca": "Hugo Boss", "referencia": "Bottled", "color": "N/A", "talla": "Única", "precio_costo": 180000, "precio": 320000, "stock": 5},
    {"codigo": "DIOR-SAV-1", "nombre": "Perfume Sauvage Dior 100ml", "categoria": "Fragancias", "marca": "Dior", "referencia": "Sauvage", "color": "N/A", "talla": "Única", "precio_costo": 280000, "precio": 480000, "stock": 4},
    {"codigo": "CHAN-BLE-1", "nombre": "Bleu de Chanel 100ml", "categoria": "Fragancias", "marca": "Chanel", "referencia": "Bleu", "color": "N/A", "talla": "Única", "precio_costo": 290000, "precio": 500000, "stock": 3},
    {"codigo": "VERS-ERO-1", "nombre": "Versace Eros Edt 100ml", "categoria": "Fragancias", "marca": "Versace", "referencia": "Eros", "color": "N/A", "talla": "Única", "precio_costo": 160000, "precio": 290000, "stock": 7},
    {"codigo": "PACO-ONE-1", "nombre": "1 Million Paco Rabanne 100ml", "categoria": "Fragancias", "marca": "Paco Rabanne", "referencia": "1Million", "color": "N/A", "talla": "Única", "precio_costo": 190000, "precio": 340000, "stock": 6},
    {"codigo": "ACQU-GIO-1", "nombre": "Acqua Di Gio Giorgio Armani", "categoria": "Fragancias", "marca": "Giorgio Armani", "referencia": "AdG", "color": "N/A", "talla": "Única", "precio_costo": 200000, "precio": 360000, "stock": 5},
    {"codigo": "CREE-AVE-1", "nombre": "Creed Aventus Eau de Parfum", "categoria": "Fragancias", "marca": "Creed", "referencia": "Aventus", "color": "N/A", "talla": "Única", "precio_costo": 450000, "precio": 850000, "stock": 2},
    {"codigo": "JEAN-LEB-1", "nombre": "Le Male Jean Paul Gaultier", "categoria": "Fragancias", "marca": "Jean Paul Gaultier", "referencia": "LeMale", "color": "N/A", "talla": "Única", "precio_costo": 195000, "precio": 350000, "stock": 4},
    {"codigo": "YSL-Y-EDP-1", "nombre": "YSL Y Eau de Parfum 100ml", "categoria": "Fragancias", "marca": "Yves Saint Laurent", "referencia": "YEdp", "color": "N/A", "talla": "Única", "precio_costo": 230000, "precio": 410000, "stock": 4},
    {"codigo": "MONT-EXP-1", "nombre": "Montblanc Explorer 100ml", "categoria": "Fragancias", "marca": "Montblanc", "referencia": "Explorer", "color": "N/A", "talla": "Única", "precio_costo": 130000, "precio": 240000, "stock": 8},

    # --- ACCESORIOS (10 registros) ---
    {"codigo": "GUCC-BEL-90", "nombre": "Cinturón de Cuero Clásico", "categoria": "Accesorios", "marca": "Gucci", "referencia": "BeltC", "color": "Negro/Dorado", "talla": "90", "precio_costo": 90000, "precio": 180000, "stock": 5},
    {"codigo": "RAY-BAN-01", "nombre": "Gafas de Sol Aviator", "categoria": "Accesorios", "marca": "Ray-Ban", "referencia": "Aviator", "color": "Dorado/Verde", "talla": "Única", "precio_costo": 150000, "precio": 290000, "stock": 4},
    {"codigo": "NEW-ERA-NY", "nombre": "Gorra New Era 9Fifty NY", "categoria": "Accesorios", "marca": "New Era", "referencia": "9Fifty", "color": "Negro", "talla": "Única", "precio_costo": 45000, "precio": 90000, "stock": 12},
    {"codigo": "NEW-ERA-LA", "nombre": "Gorra New Era 9Fifty LA", "categoria": "Accesorios", "marca": "New Era", "referencia": "9Fifty", "color": "Azul", "talla": "Única", "precio_costo": 45000, "precio": 90000, "stock": 10},
    {"codigo": "HERS-BAC-1", "nombre": "Mochila Casual Heritage", "categoria": "Accesorios", "marca": "Herschel", "referencia": "Heritage", "color": "Gris", "talla": "Única", "precio_costo": 110000, "precio": 210000, "stock": 6},
    {"codigo": "TOMM-WAL-1", "nombre": "Billetera de Cuero Genuino", "categoria": "Accesorios", "marca": "Tommy Hilfiger", "referencia": "WalletL", "color": "Marrón", "talla": "Única", "precio_costo": 50000, "precio": 100000, "stock": 9},
    {"codigo": "NIKE-SOCKS", "nombre": "Medias Deportivas Pack x3", "categoria": "Accesorios", "marca": "Nike", "referencia": "Socks3x", "color": "Blanco", "talla": "M", "precio_costo": 18000, "precio": 40000, "stock": 25},
    {"codigo": "ADID-BAG-1", "nombre": "Canguro / Riñonera Waist Bag", "categoria": "Accesorios", "marca": "Adidas", "referencia": "WaistB", "color": "Negro", "talla": "Única", "precio_costo": 35000, "precio": 75000, "stock": 8},
    {"codigo": "OAKL-SUN-1", "nombre": "Gafas Deportivas Holbrook", "categoria": "Accesorios", "marca": "Oakley", "referencia": "Holbrook", "color": "Negro Mate", "talla": "Única", "precio_costo": 170000, "precio": 320000, "stock": 3},
    {"codigo": "SWAT-WAT-1", "nombre": "Reloj Minimalista Acero", "categoria": "Accesorios", "marca": "Swatch", "referencia": "Irony", "color": "Plateado", "talla": "Única", "precio_costo": 140000, "precio": 260000, "stock": 4}
]

df = DataFrame_obj = pd.DataFrame(data)
DataFrame_obj.to_excel("inventario_50_registros.xlsx", index=False)
print("¡Archivo 'inventario_50_registros.xlsx' generado con éxito con 50 registros!")
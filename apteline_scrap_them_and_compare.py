try:

    from bs4 import BeautifulSoup
    import requests
    import pandas as pd
    from multiprocessing.pool import ThreadPool as Pool
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import datetime

    odbiorca_email = [adresy_mailowe] #hidden
    path_to_file = plik_z_danymi #hidden

    pool_size = 4
    page = requests.get(f'https://apteline.pl')
    soup = BeautifulSoup(page.content, 'html.parser')
    okno_kategorie = soup.find('div', class_="nav-categories__dropdown")

    kategorie = okno_kategorie.find_all('a', class_="level1")

    lista_kategorii = []
    for kat in kategorie:
        if 'href=' not in kat['href']:
            lista_kategorii.append(kat['href'] + '?limit=60')
            print(f'DODANO KATEGORIĘ: {kat.text}')

            page = requests.get(kat['href'])
            soup = BeautifulSoup(page.content, 'html.parser')
            okno_podkategorie = soup.find('dl', class_='nav-aside')
            if okno_podkategorie != None:
                podkategorie = okno_podkategorie.find_all('a')

            for podkat in podkategorie:
                lista_kategorii.append(podkat['href'] + '?limit=60')
                print(f'\tDODANO PODKATEGORIĘ: {podkat.text.strip()}')

    lista_nazwa_cena = []

    def mail(to, subject, text_html):  # wysylanie maila
        gmail_user = email_address #hidden
        gmail_pwd = password #hidden
        msg = MIMEMultipart()

        msg['From'] = gmail_user
        msg['To'] = to
        msg['Subject'] = subject

        msg.attach(MIMEText(text_html, 'html'))

        mailServer = smtplib.SMTP("smtp.gmail.com", 587)
        mailServer.ehlo()
        mailServer.starttls()
        mailServer.ehlo()
        mailServer.login(gmail_user, gmail_pwd)
        mailServer.sendmail(gmail_user, to, msg.as_string())
        # Should be mailServer.quit(), but that crashes...
        mailServer.close()
        print(f"wyslano do: {to}")

    def scrap_this(kat):
        print(kat)
        url_kat = kat

        page_kat = requests.get(url_kat)
        soup_kat = BeautifulSoup(page_kat.content, 'html.parser')
        div_strony = soup_kat.find('div', class_="pages pagination")
        if div_strony != None:
            strony = div_strony.find('span')
            ilosc_stron = int(str(strony).split()[2])
        else:
            ilosc_stron = 1

        for p in range(1,ilosc_stron+1):
            url_kat_page = url_kat + f'&p={p}'
            page = requests.get(f'{url_kat_page}')
            soup = BeautifulSoup(page.content, 'html.parser')

            okno_wynikow_nazwa = soup.find_all('div', class_="product-item__desc")
            nazwy_lista = []
            link_lista = []

            for okno in okno_wynikow_nazwa:
                nazwa = okno.find('a')
                link = okno.find('a')['href']
                nazwy_lista.append(nazwa.text.strip())
                link_lista.append(link)

            okno_wynikow_cena = soup.find_all('div', class_="product-item__shop")

            ceny_lista = []

            for okno in okno_wynikow_cena:
                cena = okno.find('span', class_='price')
                if cena != None:
                    ceny_lista.append(float(cena.text.strip().replace('\xa0zł', '').replace(',', '.')))
                else:
                    ceny_lista.append('brak ceny')

            for i in range(0, len(nazwy_lista)):
                lista_nazwa_cena.append([nazwy_lista[i], ceny_lista[i], link_lista[i]])

    pool = Pool(pool_size)
    for item in lista_kategorii:
        pool.apply_async(scrap_this, (item,))

    pool.close()
    pool.join()

    df = pd.DataFrame(lista_nazwa_cena)
    df.columns = ['nazwa', 'cena', 'link']
    df = df.drop_duplicates(subset=['nazwa'])
    puste_linie_filtr = df[df['cena'] == 'brak ceny'].index
    df.drop(puste_linie_filtr, inplace=True)
    df.sort_values(by='nazwa', inplace=True, ascending=True)

    df_last = pd.read_excel(fr'{path_to_file}')

    merge_result = pd.merge(df_last, df, how='outer', on=['nazwa'])
    merge_result.columns = ['nazwa','cena_stara', 'link_1', 'cena_nowa', 'link_2']

    #obrobka do zapisu pliku bazowego
    filtr_stary_link_nan = merge_result[merge_result['link_1'].isnull() == True].index
    merge_result.loc[filtr_stary_link_nan, 'link_1'] = merge_result.loc[filtr_stary_link_nan, 'link_2']
    filtr_cena_nowa_nan = merge_result[merge_result['cena_nowa'].isnull() == True].index
    merge_result.loc[filtr_cena_nowa_nan, 'cena_nowa'] = merge_result.loc[filtr_cena_nowa_nan, 'cena_stara']
    df_obrobka_do_zapisu = merge_result[['nazwa', 'cena_nowa', 'link_1']].copy()
    df_obrobka_do_zapisu.sort_values(by='nazwa', inplace=True, ascending=True)
    df_obrobka_do_zapisu = df_obrobka_do_zapisu.drop_duplicates()
    df_obrobka_do_zapisu.to_excel(fr'{path_to_file}', index=False)

    #znajdowanie malejacych cen
    filtr = merge_result[merge_result['cena_nowa']-merge_result['cena_stara'] < 0].index
    df_zmniejszona_cena = merge_result.loc[filtr][['nazwa', 'cena_stara', 'cena_nowa', 'link_1']]


    df_lista = df_zmniejszona_cena.values.tolist()

    if df_lista != []:
    #przygotowanie tekstu wiadomosci mailowej
        text_html ='''
                <html>
                    <head>
                        <style type="text/css">
                            .tg  {width: 80%;border-collapse:collapse;border-spacing:0;margin:0px auto;}
                            .tg td{font-family:Arial, sans-serif;font-size:14px;padding:7px 10px;border-style:solid;border-width:1px;overflow:hidden;word-break:normal;border-color:black;}
                            .tg th{font-family:Arial, sans-serif;font-size:14px;font-weight:normal;padding:7px 10px;border-style:solid;border-width:1px;overflow:hidden;word-break:normal;border-color:black;}
                            .tg .tg-7acn{font-weight:bold;font-size:16px;font-family:Verdana, Geneva, sans-serif !important;;background-color:#a79d9d;color:#000000;text-align:center;vertical-align:middle}
                            .tg .tg-8jxh{font-weight:bold;font-size:20px;font-family:Verdana, Geneva, sans-serif !important;;background-color:#a79d9d;color:#000000;text-align:center;vertical-align:middle}
                            .tg .tg-8p8o{font-weight:bold;font-size:13px;font-family:Verdana, Geneva, sans-serif !important;;background-color:#d4d2d2;color:#000000;text-align:center;vertical-align:middle}
                        </style>
                        <table class="tg">
                          <tr>
                            <th class="tg-8jxh" colspan="5"> WYKAZ PRODUKTÓW Z OBNIŻONĄ CENĄ W APTELINE.PL</th>
                          </tr>
                          <tr>
                            <td class="tg-7acn">LP</td>
                            <td class="tg-7acn">NAZWA</td>
                            <td class="tg-7acn">CENA BRUTTO</td>
                            <td class="tg-7acn">ZMIANA</td>
                            <td class="tg-7acn">LINK</td>
                           </tr>'''
        n = 1
        for d in df_lista:

            text_html += f'<tr>' \
                         f'<td class="tg-8p8o">{n}</td>' \
                         f'<td class="tg-8p8o">{d[0]}</td>' \
                         f'<td class="tg-8p8o">{d[2]:.2f} zł</td>' \
                         f'<td class="tg-8p8o">{(d[2]-d[1]):.2f} zł</td>' \
                         f'<td class="tg-8p8o">{d[3]}</td>' \
                         f'</tr>\n'
            print(d)
            n+=1

        text_html += '</table>'
        for odbiorca in odbiorca_email:
            mail(odbiorca, f'OBNIŻKI CEN NA APTELINE.PL - {str(datetime.datetime.now())[0:19]}. POZYCJE - {len(df_lista)}',text_html)

    else:
        text_html = ''
        # mail(odbiorca_email, 'OBNIŻKI CEN NA APTELINE.PL - NIC NOWEGO', text_html)

except Exception as ex:
    print(ex)
    koniec = input('Naciśnij ENTER żeby zamknąć program.')
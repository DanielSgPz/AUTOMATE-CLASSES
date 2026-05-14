async def login_generico(page, url, username, password):
    await page.goto(url)
    
    # Uso '#' para indicarle a Playwright que busque por ID
    await page.fill('#vUSUCOD', username) 
    await page.fill('#vPASS', password)
    
    # El botón no es tipo "submit", tiene el ID "BUTTON1"
    await page.click('#BUTTON1')
    
    await page.wait_for_load_state("networkidle")
    print(f"Proceso de login ejecutado en {url}")
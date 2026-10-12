const menu = [
  {category:'mic-dejun', title:'Mic dejun', items:[['Croissant cu unt','10 lei'],['Croissant cu șuncă și cașcaval','18 lei'],['Omletă cu bacon și cașcaval','29 lei'],['Avocado toast cu ou','28 lei'],['Mic dejun Bistro','34 lei']]},
  {category:'cafea', title:'Cafea', items:[['Espresso','9 lei'],['Espresso dublu','12 lei'],['Americano','10 lei'],['Cappuccino','14 lei'],['Latte','15 lei'],['Flat White','16 lei'],['Caffè Mocha','17 lei'],['Iced Latte','16 lei']]},
  {category:'gustari', title:'Gustări sărate', items:[['Sandviș cu șuncă și cașcaval','19 lei'],['Panini cu pui','23 lei'],['Toast cu mozzarella și roșii','18 lei'],['Bagel cu cremă de brânză','17 lei']]},
  {category:'desert', title:'Gustări dulci', items:[['Croissant cu unt','9 lei'],['Croissant cu ciocolată','12 lei'],['Muffin','10 lei'],['Cheesecake','18 lei'],['Brownie cu ciocolată','14 lei'],['Tiramisu','17 lei']]},
  {category:'cafea', title:'Ceaiuri & ciocolată', items:[['Ceai aromat','10 lei'],['Ceai cu miere și lămâie','12 lei'],['Ciocolată caldă','15 lei'],['Matcha Latte','18 lei']]},
  {category:'reci', title:'Băuturi reci', items:[['Iced Latte','16 lei'],['Iced Americano','12 lei'],['Frappé','17 lei'],['Espresso Tonic','18 lei'],['Fresh de portocale','18 lei'],['Limonadă clasică','14 lei']]},
  {category:'cocktailuri', title:'Cocktailuri alcoolice', items:[['Mojito','25 lei'],['Aperol Spritz','28 lei'],['Margarita','27 lei'],['Piña Colada','29 lei'],['Sex on the Beach','27 lei'],['Gin Tonic','24 lei']]},
  {category:'cocktailuri', title:'Cocktailuri nonalcoolice', items:[['Tropical Sunrise','18 lei'],['Virgin Piña Colada','20 lei'],['Strawberry Lemonade','16 lei'],['Blue Lagoon fără alcool','18 lei'],['Mango Cooler','19 lei']]},
  {category:'copii', title:'Meniu pentru copii', items:[['Micul explorator · mini sandviș și limonadă','20 lei'],['Micul bucătar · mini pizza și suc','25 lei'],['Micul pofticios · clătite cu ciocolată și lapte','24 lei'],['Micul răsfățat · waffles cu fructe și smoothie','28 lei']]},
  {category:'toamna', title:'Băuturi calde de sezon', items:[['Pumpkin Spice Latte','19 lei'],['Latte cu scorțișoară','17 lei'],['Caramel Macchiato','18 lei'],['Ciocolată caldă cu frișcă','17 lei'],['Cappuccino cu aromă de alune','18 lei']]},
  {category:'toamna', title:'Deserturi de sezon', items:[['Cheesecake cu dovleac','15 lei'],['Ruladă cu scorțișoară','16 lei'],['Crumble cu mere','19 lei'],['Brownie cu nuci','14 lei'],['Gogoși cu mere','17 lei'],['Waffles cu caramel și nuci','15 lei'],['Clătite cu mere caramelizate','13 lei']]},
];

const menuGrid = document.querySelector('#menu-grid');
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let revealObserver;

if ('IntersectionObserver' in window && !reduceMotion) {
  document.documentElement.classList.add('has-motion');
  revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {threshold: 0.12, rootMargin: '0px 0px -28px 0px'});
}

function observeRevealElements(root=document) {
  const elements = root.querySelectorAll('[data-reveal]:not(.is-visible)');
  elements.forEach((element, index) => {
    element.style.setProperty('--reveal-delay', `${Math.min(index % 4, 3) * 75}ms`);
    revealObserver?.observe(element);
  });
}

document.querySelectorAll('.section-kicker, .intro h2, .intro-text, .value-strip > div, .section-heading, .menu-tabs, .event-row, .event-note, .offer-details, .spaces-grid .space-card, .space-prices > div, .contact-left, .contact-right, .request-heading, .request-form').forEach(element => element.dataset.reveal = '');
observeRevealElements();

function renderMenu(filter='toate') {
  const sections = menu.filter(section => filter === 'toate' || section.category === filter);
  menuGrid.innerHTML = sections.map(section => `
    <section class="menu-category" data-reveal><h3>${section.title}</h3>${section.items.map(([name, detail]) => `
      <div class="menu-item"><b>${name}</b><span>${detail}</span></div>`).join('')}
    </section>`).join('');
  observeRevealElements(menuGrid);
}
renderMenu();

document.querySelectorAll('.menu-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelector('.menu-tab.active')?.classList.remove('active');
    document.querySelector('.menu-tab[aria-selected="true"]')?.setAttribute('aria-selected', 'false');
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    renderMenu(tab.dataset.category);
  });
});

const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('.site-nav');
toggle.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') !== 'true';
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', open ? 'Închide meniul' : 'Deschide meniul');
  nav.classList.toggle('open', open);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open');
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', 'Deschide meniul');
}));
document.querySelector('#year').textContent = new Date().getFullYear();

const progressBar = document.querySelector('.scroll-progress > span');
const navigationLinks = [...document.querySelectorAll('.site-nav a[href^="#"]')];
function updatePagePosition() {
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const progress = scrollable > 0 ? window.scrollY / scrollable : 0;
  progressBar.style.transform = `scaleX(${progress})`;

  let current = '';
  navigationLinks.forEach(link => {
    const section = document.querySelector(link.getAttribute('href'));
    if (section && section.getBoundingClientRect().top <= 145) current = link.getAttribute('href');
  });
  navigationLinks.forEach(link => {
    if (link.getAttribute('href') === current) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
}
window.addEventListener('scroll', updatePagePosition, {passive:true});
window.addEventListener('resize', updatePagePosition);
updatePagePosition();
